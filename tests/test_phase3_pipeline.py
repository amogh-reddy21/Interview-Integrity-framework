"""Phase 3 plumbing, on the real fixtures, with the model stubbed.

This does not test the prompt -- only that transcript rendering, JSON parsing,
the deterministic filters, contract construction, the runner's comparison
against pre-committed expectations, and the verbatim check all work on actual
fixture data. Running it first means the first live API call is testing the
prompt rather than the wiring.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from run_fixtures import load_fixtures, run_one  # noqa: E402
from verbatim_check import verbatim_failures  # noqa: E402

from integrity import contradictions as C  # noqa: E402
from integrity.adapters.transcript import from_raw  # noqa: E402

# The pair fixture 7 plants, quoted from the fixture's own answer text.
FIXTURE_7_PAIR = {
    "statement_a": "I led a team of four on the migration",
    "statement_b": "Honestly it was mostly just me. I did not really have help on that one",
    "turn_a": "a2",
    "turn_b": "a8",
    "conflict_type": "team_size",
    "explanation": "A led team of four cannot also be work done essentially alone.",
}


def oracle(fixture_id: int):
    """A stub that behaves like a perfect model: fires only on fixture 7."""

    def _complete(prompt: str, schema=None):
        if "both_can_be_true" in prompt or "burden of proof" in prompt:
            return json.dumps({"both_can_be_true": False, "reason": "incompatible"})
        payload = [FIXTURE_7_PAIR] if fixture_id == 7 else []
        return json.dumps({"contradictions": payload})

    return _complete


class Phase3Pipeline(unittest.TestCase):
    def test_fixtures_pass_with_a_perfect_model(self):
        for doc in load_fixtures():
            fid = doc["fixture"]["id"]
            with self.subTest(fixture=doc["fixture"]["name"]):
                with mock.patch.object(C, "complete", oracle(fid)):
                    report, failures = run_one(doc)
                self.assertEqual(failures, [], f"{fid}: {failures}")
                self.assertEqual(
                    verbatim_failures(report, from_raw(doc["raw"])),
                    [],
                    f"{fid}: quotes are not verbatim",
                )

    def test_planted_quotes_really_are_in_fixture_7(self):
        """Guards the stub itself: if the fixture text changed, this fails."""
        doc = next(d for d in load_fixtures() if d["fixture"]["id"] == 7)
        answers = {t["turn_id"]: t["text"] for t in doc["raw"]["turns"]}
        self.assertIn(FIXTURE_7_PAIR["statement_a"], answers["a2"])
        self.assertIn(FIXTURE_7_PAIR["statement_b"], answers["a8"])

    def test_rendered_report_shows_both_quotes(self):
        from integrity.render import render

        doc = next(d for d in load_fixtures() if d["fixture"]["id"] == 7)
        with mock.patch.object(C, "complete", oracle(7)):
            report, _ = run_one(doc)
        text = render(report)
        self.assertIn(FIXTURE_7_PAIR["statement_a"], text)
        self.assertIn(FIXTURE_7_PAIR["statement_b"], text)
        self.assertIn("a2", text)
        self.assertIn("a8", text)
        self.assertIn("Absence of findings", text)

    def test_a_model_that_fires_on_everything_fails_the_gate(self):
        """The gate must be capable of failing. Fire a plausible-looking pair
        on every fixture and assert the false-positive fixtures reject it."""

        def trigger_happy(prompt: str, schema=None):
            if "both_can_be_true" in prompt or "burden of proof" in prompt:
                return json.dumps({"both_can_be_true": False, "reason": "x"})
            # Quote the first two candidate answers verbatim out of the prompt.
            answers = [
                line.split("CANDIDATE: ", 1)[1]
                for line in prompt.splitlines()
                if "CANDIDATE: " in line
            ]
            ids = [
                line.split("]")[0].lstrip("[")
                for line in prompt.splitlines()
                if "CANDIDATE: " in line
            ]
            if len(answers) < 2:
                return json.dumps({"contradictions": []})
            return json.dumps({"contradictions": [{
                "statement_a": answers[0],
                "statement_b": answers[1],
                "turn_a": ids[0],
                "turn_b": ids[1],
                "conflict_type": "scope",
                "explanation": "manufactured",
            }]})

        failed_gate = []
        for doc in load_fixtures():
            if doc["fixture"]["id"] not in (8, 9, 10, 11):
                continue
            with mock.patch.object(C, "complete", trigger_happy):
                _, failures = run_one(doc)
            if failures:
                failed_gate.append(doc["fixture"]["id"])
        self.assertEqual(
            sorted(failed_gate),
            [8, 9, 10, 11],
            "a model firing on every transcript did not fail the false-positive "
            "fixtures, so those fixtures are not actually gating anything",
        )


if __name__ == "__main__":
    unittest.main()
