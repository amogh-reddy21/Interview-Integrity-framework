"""Fixture expectations, offline.

These run without an API key. The LLM is stubbed to return nothing, which
checks the parts of the pipeline that are deterministic: every fixture whose
expectation is silence must still be silent when the model proposes nothing,
and every quote that does survive must be verbatim.

The live run -- the one that actually exercises the model -- is
tools/run_fixtures.py, which costs money and is not a unit test.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from run_fixtures import load_fixtures  # noqa: E402
from verbatim_check import verbatim_failures  # noqa: E402

from integrity import contradictions as contra  # noqa: E402
from integrity.adapters.transcript import from_raw  # noqa: E402
from integrity.analyze import assemble  # noqa: E402

SILENT_FIXTURES = {1, 2, 3, 4, 5, 6, 8, 9, 10, 11}


def run_offline(doc):
    """Run a fixture with an LLM that proposes nothing."""
    transcript = from_raw(doc["raw"])
    with mock.patch.object(contra, "complete", return_value='{"pairs": []}'):
        found, coverage = contra.find_contradictions(transcript)
    return assemble(coverage, found), transcript


class Fixtures(unittest.TestCase):
    def test_every_fixture_parses(self):
        for doc in load_fixtures():
            with self.subTest(fixture=doc["fixture"]["name"]):
                transcript = from_raw(doc["raw"])
                self.assertGreater(len(transcript.exchanges), 0)

    def test_silent_fixtures_stay_silent_offline(self):
        """The ship gate: ten of eleven fixtures are at zero. Written down so
        it is not renegotiated later."""
        for doc in load_fixtures():
            if doc["fixture"]["id"] not in SILENT_FIXTURES:
                continue
            report, _ = run_offline(doc)
            with self.subTest(fixture=doc["fixture"]["name"]):
                self.assertEqual(report.contradictions, [])

    def test_every_quote_is_verbatim(self):
        for doc in load_fixtures():
            with self.subTest(fixture=doc["fixture"]["name"]):
                report, transcript = run_offline(doc)
                self.assertEqual(verbatim_failures(report, transcript), [])

    def test_standing_caveat_is_always_present(self):
        from integrity.analyze import STANDING_CAVEAT

        for doc in load_fixtures():
            report, _ = run_offline(doc)
            with self.subTest(fixture=doc["fixture"]["name"]):
                self.assertIn(STANDING_CAVEAT, report.coverage_note)


if __name__ == "__main__":
    unittest.main()
