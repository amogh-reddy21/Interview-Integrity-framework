"""The only file that changes when we see the interview platform's format.

Everything downstream consumes contract.Transcript, so integrating with the
real agent should be an edit here, not a rewrite.

Expected raw shape:

    {
      "interview_id": "...",
      "candidate_id": "...",
      "turns": [
        {"turn_id": "q1", "speaker": "agent",     "text": "...",
         "question_bucket": "factual"},
        {"turn_id": "a1", "speaker": "candidate", "text": "..."}
      ]
    }

Timestamps (``start_ts`` / ``end_ts``) are accepted and carried through if the
platform supplies them, but nothing reads them -- no analysis in this system
depends on how long a candidate took to answer. A transcript with no timing at
all is fully supported.
"""

from __future__ import annotations

from typing import Any, Optional

from ..contract import AnswerTurn, BUCKETS, Exchange, QuestionTurn, Transcript

AGENT_SPEAKERS = {"agent", "interviewer", "assistant", "system"}
CANDIDATE_SPEAKERS = {"candidate", "user", "interviewee"}


def from_raw(raw: dict[str, Any]) -> Transcript:
    turns = raw.get("turns") or []
    if not turns:
        raise ValueError("transcript has no turns")

    exchanges: list[Exchange] = []
    pending: Optional[QuestionTurn] = None

    for turn in turns:
        speaker = str(turn.get("speaker", "")).lower()
        if speaker in AGENT_SPEAKERS:
            if pending is not None:
                # Agent asked again without an answer in between. The earlier
                # question stands as an exchange with no answer.
                exchanges.append(Exchange(question=pending, answer=None))
            pending = _question(turn)
        elif speaker in CANDIDATE_SPEAKERS:
            if pending is None:
                continue  # candidate speech not in response to a question
            exchanges.append(Exchange(question=pending, answer=_answer(turn)))
            pending = None
        else:
            raise ValueError(f"unknown speaker: {turn.get('speaker')!r}")

    if pending is not None:
        exchanges.append(Exchange(question=pending, answer=None))

    if not any(e.answer is not None for e in exchanges):
        raise ValueError("transcript contains no candidate answers")

    return Transcript(
        interview_id=str(raw.get("interview_id", "unknown")),
        exchanges=tuple(exchanges),
        candidate_id=raw.get("candidate_id"),
        source=raw.get("source"),
    )


def _ts(turn: dict[str, Any], key: str) -> Optional[float]:
    value = turn.get(key)
    return float(value) if value is not None else None


def _question(turn: dict[str, Any]) -> QuestionTurn:
    text = str(turn.get("text", ""))
    return QuestionTurn(
        turn_id=str(turn.get("turn_id")),
        text=text,
        bucket=_bucket(turn, text),
        question_id=turn.get("question_id"),
        start_ts=_ts(turn, "start_ts"),
        end_ts=_ts(turn, "end_ts"),
    )


def _answer(turn: dict[str, Any]) -> AnswerTurn:
    return AnswerTurn(
        turn_id=str(turn.get("turn_id")),
        text=str(turn.get("text", "")),
        start_ts=_ts(turn, "start_ts"),
        end_ts=_ts(turn, "end_ts"),
    )


def _bucket(turn: dict[str, Any], text: str) -> Optional[str]:
    """Resolve the question bucket. Never guessed from the question's wording.

    Explicit field first, then the question pool by id, then the pool by exact
    text. Buckets describe how an interview is composed (Phase 2); no finding
    depends on them.
    """
    explicit = turn.get("question_bucket") or turn.get("bucket")
    if explicit:
        if explicit not in BUCKETS:
            raise ValueError(f"unknown bucket {explicit!r} on {turn.get('turn_id')!r}")
        return str(explicit)

    try:
        from ..question_pool import bucket_for
    except ImportError:  # pragma: no cover - pool is part of this package
        return None
    return bucket_for(turn.get("question_id"), text)
