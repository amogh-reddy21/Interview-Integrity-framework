"""Deterministic tests for the Phase 3 filters. No API key needed.

The LLM's proposal is stubbed so the filter chain can be tested on its own.
These are the suppressions that must hold regardless of what the model says,
which is why they live in code rather than in the prompt.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from integrity import contradictions as C  # noqa: E402
from integrity.contract import AnswerTurn, Exchange, QuestionTurn, Transcript  # noqa: E402


def transcript() -> Transcript:
    turns = [
        ("q1", "How big was the team?", "a1", "There were four of us on it, sorry, five with the intern."),
        ("q2", "Who did the work?", "a2", "I led a team of four on the migration."),
        ("q3", "How was it divided?", "a3", "It was mostly just me. I did not really have help on that one."),
    ]
    return Transcript(
        interview_id="t",
        exchanges=tuple(
            Exchange(
                question=QuestionTurn(turn_id=q, text=qt, end_ts=float(i * 10), bucket="experiential"),
                answer=AnswerTurn(turn_id=a, text=at, start_ts=float(i * 10 + 1)),
            )
            for i, (q, qt, a, at) in enumerate(turns)
        ),
    )


def stub(proposal: list[dict]):
    """Return a fake complete() that answers extract then verify calls."""
    def _complete(prompt: str, schema=None):
        if "both_can_be_true" in prompt or "burden of proof" in prompt:
            return json.dumps({"both_can_be_true": False, "reason": "genuinely incompatible"})
        return json.dumps({"contradictions": proposal})
    return _complete


class DeterministicFilters(unittest.TestCase):
    def run_with(self, proposal):
        with mock.patch.object(C, "complete", stub(proposal)):
            return C.find_contradictions(transcript())

    def test_same_turn_pair_is_dropped(self):
        found, coverage = self.run_with([{
            "statement_a": "There were four of us on it",
            "statement_b": "five with the intern",
            "turn_a": "a1", "turn_b": "a1",
            "conflict_type": "team_size", "explanation": "four vs five",
        }])
        self.assertEqual(found, [])
        self.assertTrue(any("same answer" in c for c in coverage), coverage)

    def test_invented_quote_is_dropped(self):
        found, coverage = self.run_with([{
            "statement_a": "I led a team of six on the migration.",
            "statement_b": "It was mostly just me.",
            "turn_a": "a2", "turn_b": "a3",
            "conflict_type": "team_size", "explanation": "six vs alone",
        }])
        self.assertEqual(found, [])
        self.assertTrue(any("verbatim" in c for c in coverage), coverage)

    def test_correction_marker_before_quote_is_dropped(self):
        found, coverage = self.run_with([{
            "statement_a": "five with the intern.",
            "statement_b": "I led a team of four on the migration.",
            "turn_a": "a1", "turn_b": "a2",
            "conflict_type": "team_size", "explanation": "five vs four",
        }])
        self.assertEqual(found, [])
        self.assertTrue(any("correction marker" in c for c in coverage), coverage)

    def test_unknown_conflict_type_is_dropped(self):
        found, _ = self.run_with([{
            "statement_a": "I led a team of four on the migration.",
            "statement_b": "It was mostly just me.",
            "turn_a": "a2", "turn_b": "a3",
            "conflict_type": "vibe", "explanation": "x",
        }])
        self.assertEqual(found, [])

    def test_unknown_turn_is_dropped(self):
        found, _ = self.run_with([{
            "statement_a": "I led a team of four on the migration.",
            "statement_b": "It was mostly just me.",
            "turn_a": "a2", "turn_b": "a99",
            "conflict_type": "team_size", "explanation": "x",
        }])
        self.assertEqual(found, [])

    def test_a_real_pair_survives(self):
        """The filters must not be so strict that nothing can ever pass."""
        found, _ = self.run_with([{
            "statement_a": "I led a team of four on the migration.",
            "statement_b": "It was mostly just me.",
            "turn_a": "a2", "turn_b": "a3",
            "conflict_type": "team_size", "explanation": "a team of four versus working alone",
        }])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].conflict_type, "team_size")
        self.assertEqual((found[0].turn_a, found[0].turn_b), ("a2", "a3"))

    def test_verification_can_veto(self):
        def veto(prompt, schema=None):
            if "both_can_be_true" in prompt or "burden of proof" in prompt:
                return json.dumps({"both_can_be_true": True, "reason": "compatible readings exist"})
            return json.dumps({"contradictions": [{
                "statement_a": "I led a team of four on the migration.",
                "statement_b": "It was mostly just me.",
                "turn_a": "a2", "turn_b": "a3",
                "conflict_type": "team_size", "explanation": "x",
            }]})
        with mock.patch.object(C, "complete", veto):
            found, coverage = C.find_contradictions(transcript())
        self.assertEqual(found, [])
        self.assertTrue(any("verification found" in c for c in coverage), coverage)

    def test_no_provider_is_not_a_crash(self):
        from integrity.adapters.llm import LLMUnavailable

        def unavailable(prompt, schema=None):
            raise LLMUnavailable("no key")

        with mock.patch.object(C, "complete", unavailable):
            found, coverage = C.find_contradictions(transcript())
        self.assertEqual(found, [])
        self.assertTrue(any("did not run" in c for c in coverage), coverage)


if __name__ == "__main__":
    unittest.main()
