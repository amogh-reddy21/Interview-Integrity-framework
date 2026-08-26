"""Scope discipline as an executable check.

Two things are enforced here that would otherwise be enforced only by
remembering them at 6pm on day 2:

1. No field anywhere in the data contract asserts a judgement -- no score,
   level, risk, confidence, or composite. An agent asked to build a detector
   will offer to add a confidence score; this test refuses it.
2. The fixtures are frozen. If a fixture fails, the detector gets fixed. This
   test compares fixture hashes against the manifest written before any
   detector code existed, so editing a fixture to make a test pass shows up as
   a failing test rather than a quiet deletion of the check.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from integrity import contract  # noqa: E402

BANNED = (
    "score",
    "level",
    "risk",
    "confidence",
    "likelihood",
    "probability",
    "rating",
    "composite",
    "severity",
    "suspicion",
    "verdict",
    "cheat",
    "flag_count",
    "total",
)

ALLOWED_EXCEPTIONS: set[str] = set()


class NoJudgementFields(unittest.TestCase):
    def test_no_banned_field_names(self):
        offenders = []
        for name in dir(contract):
            obj = getattr(contract, name)
            if not dataclasses.is_dataclass(obj):
                continue
            for field in dataclasses.fields(obj):
                if field.name in ALLOWED_EXCEPTIONS:
                    continue
                lowered = field.name.lower()
                for banned in BANNED:
                    if banned in lowered:
                        offenders.append(f"{name}.{field.name} contains {banned!r}")
        self.assertEqual(
            offenders,
            [],
            "the data contract grew a judgement field: " + "; ".join(offenders),
        )

    def test_report_has_exactly_the_agreed_fields(self):
        names = [f.name for f in dataclasses.fields(contract.IntegrityReport)]
        self.assertEqual(names, ["contradictions", "coverage_note"])

    def test_empty_report_is_constructible(self):
        """A clean interview is a success case, not an error path."""
        report = contract.IntegrityReport()
        self.assertEqual(report.contradictions, [])
        self.assertEqual(report.coverage_note, "")


class FixturesAreFrozen(unittest.TestCase):
    def test_hashes_match_manifest(self):
        manifest = os.path.join(ROOT, "fixtures", "FROZEN.txt")
        expected = {}
        with open(manifest) as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                digest, name = line.split()
                expected[name] = digest

        self.assertEqual(len(expected), 11, "expected 11 frozen fixtures")
        for name, digest in expected.items():
            path = os.path.join(ROOT, "fixtures", name)
            with open(path, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(
                actual,
                digest,
                f"{name} has changed since it was frozen. If a fixture is "
                "failing, fix the detector -- editing the fixture deletes the "
                "check. If the change is deliberate, update FROZEN.txt in the "
                "same commit and say why.",
            )

    def test_every_fixture_has_a_precommitted_expectation(self):
        import glob
        import json

        for path in sorted(glob.glob(os.path.join(ROOT, "fixtures", "fixture_*.json"))):
            with open(path) as f:
                doc = json.load(f)
            self.assertIn("expected", doc, path)
            self.assertIn("expected_note", doc, path)
            self.assertIn("contradictions", doc["expected"], path)


if __name__ == "__main__":
    unittest.main()
