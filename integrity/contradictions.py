"""Phase 3 -- contradictions.

Two statements in one transcript that cannot both be true. Structure is
extract, then filter deterministically, then verify:

  1. One LLM pass over the transcript proposes candidates.
  2. Deterministic filters drop anything structurally invalid. These are the
     suppressions that must never depend on a model's mood -- a quote that is
     not in the transcript, or a "contradiction" between two halves of one
     sentence, is thrown out in code.
  3. A second LLM pass re-examines each survivor in isolation, with the burden
     of proof on the detector, and drops it if both statements could be true.

Stage 2 is what makes self-corrections safe: a candidate correcting themselves
mid-answer produces both quotes inside a single turn, and same-turn pairs are
rejected without a model in the loop.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from .adapters.llm import LLMUnavailable, complete
from .contract import Contradiction, Transcript
from .prompts import EXTRACT, EXTRACT_SCHEMA, VERIFY, VERIFY_SCHEMA

CONFLICT_TYPES = {
    "team_size",
    "ownership",
    "timeline",
    "scope",
    "technology",
    "role",
    "quantified_outcome",
}

#: Spoken markers of a correction in progress. Used only to drop candidates,
#: never to create one.
CORRECTION_MARKERS = (
    "sorry",
    "actually",
    "i mean",
    "i meant",
    "no, wait",
    "or rather",
    "i misspoke",
    "i forgot",
    "correction",
    "let me rephrase",
    "scratch that",
)


def find_contradictions(
    transcript: Transcript, verify: bool = True
) -> tuple[list[Contradiction], list[str]]:
    """Return (contradictions, coverage_lines)."""
    answers = {
        e.answer.turn_id: e.answer.text
        for e in transcript.exchanges
        if e.answer is not None
    }
    if len(answers) < 2:
        return [], ["Contradiction analysis skipped: fewer than two candidate answers."]

    try:
        raw = complete(EXTRACT.format(transcript=_render(transcript)), EXTRACT_SCHEMA)
    except LLMUnavailable as exc:
        return [], [f"Contradiction analysis did not run: {exc}"]

    proposed = _parse(raw)
    coverage: list[str] = []
    kept: list[Contradiction] = []
    dropped: list[str] = []

    for item in proposed:
        reason = _structural_reject(item, answers)
        if reason:
            dropped.append(f"{item.get('turn_a')}/{item.get('turn_b')}: {reason}")
            continue
        if verify:
            verdict = _verify(item, answers)
            if verdict is not None:
                dropped.append(f"{item['turn_a']}/{item['turn_b']}: {verdict}")
                continue
        kept.append(
            Contradiction(
                statement_a=item["statement_a"],
                statement_b=item["statement_b"],
                turn_a=item["turn_a"],
                turn_b=item["turn_b"],
                conflict_type=item["conflict_type"],
                explanation=item["explanation"],
            )
        )

    coverage.append(
        f"Contradiction analysis examined {len(answers)} candidate answers; "
        f"{len(proposed)} candidate pair(s) proposed, {len(kept)} kept."
    )
    for line in dropped:
        coverage.append(f"Suppressed -- {line}")
    return kept, coverage


def _render(transcript: Transcript) -> str:
    lines = []
    for exchange in transcript.exchanges:
        q = exchange.question
        lines.append(f"[{q.turn_id}] INTERVIEWER: {q.text}")
        if exchange.answer is not None:
            lines.append(f"[{exchange.answer.turn_id}] CANDIDATE: {exchange.answer.text}")
    return "\n".join(lines)


def _parse(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    items = data.get("contradictions") if isinstance(data, dict) else data
    return [i for i in (items or []) if isinstance(i, dict)]


def _structural_reject(item: dict[str, Any], answers: dict[str, str]) -> Optional[str]:
    """Deterministic suppressions. No model involved, so they cannot regress."""
    required = ("statement_a", "statement_b", "turn_a", "turn_b", "conflict_type", "explanation")
    missing = [f for f in required if not item.get(f)]
    if missing:
        return f"malformed candidate, missing {missing}"

    if item["conflict_type"] not in CONFLICT_TYPES:
        return f"conflict_type {item['conflict_type']!r} is not in the contract"

    if item["turn_a"] == item["turn_b"]:
        return (
            "both quotes come from the same answer, which is a self-correction "
            "or a restatement rather than a contradiction between two claims"
        )

    for side in ("a", "b"):
        turn_id = item[f"turn_{side}"]
        quote = item[f"statement_{side}"]
        if turn_id not in answers:
            return f"turn {turn_id} is not a candidate answer in this transcript"
        if quote not in answers[turn_id]:
            return (
                f"statement_{side} is not a verbatim substring of turn {turn_id}; "
                "the quote was altered or invented"
            )

    if _is_correction(item, answers):
        return "the later statement is preceded by an explicit self-correction marker"

    return None


def _is_correction(item: dict[str, Any], answers: dict[str, str]) -> bool:
    """True if a correction marker immediately precedes either quote.

    Only the text just before the quote is considered. A "sorry" elsewhere in a
    long answer says nothing about this sentence.
    """
    for side in ("a", "b"):
        text = answers[item[f"turn_{side}"]]
        quote = item[f"statement_{side}"]
        idx = text.find(quote)
        if idx <= 0:
            continue
        preceding = text[max(0, idx - 40) : idx].lower()
        if any(marker in preceding for marker in CORRECTION_MARKERS):
            return True
    return False


def _verify(item: dict[str, Any], answers: dict[str, str]) -> Optional[str]:
    """Second pass. Returns a suppression reason, or None to keep."""
    prompt = VERIFY.format(
        turn_a=item["turn_a"],
        turn_b=item["turn_b"],
        statement_a=item["statement_a"],
        statement_b=item["statement_b"],
        context_a=answers[item["turn_a"]],
        context_b=answers[item["turn_b"]],
        conflict_type=item["conflict_type"],
        explanation=item["explanation"],
    )
    try:
        raw = complete(prompt, VERIFY_SCHEMA)
    except LLMUnavailable as exc:
        return f"could not be verified ({exc}), so it was not reported"

    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        return "verification returned unparseable output, so it was not reported"

    if verdict.get("both_can_be_true", True):
        return f"verification found both statements can be true: {verdict.get('reason', '')}"
    return None
