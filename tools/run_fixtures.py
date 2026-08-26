#!/usr/bin/env python3
"""Run every fixture and compare against its pre-committed expectation.

Every fixture calls the LLM, so this costs money and needs ANTHROPIC_API_KEY.
Set INTEGRITY_LLM_CACHE_DIR to reuse previous responses and make repeat runs
free and repeatable.

Usage:
  python3 tools/run_fixtures.py
  python3 tools/run_fixtures.py --show 7      # print the rendered report
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrity.adapters.transcript import from_raw  # noqa: E402
from integrity.analyze import assemble  # noqa: E402
from integrity.contract import IntegrityReport  # noqa: E402
from integrity.contradictions import find_contradictions  # noqa: E402
from integrity.render import render  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_GLOB = os.path.join(ROOT, "fixtures", "fixture_*.json")


def load_fixtures() -> list[dict]:
    out = []
    for path in sorted(glob.glob(FIXTURE_GLOB)):
        with open(path) as f:
            doc = json.load(f)
        doc["_path"] = path
        out.append(doc)
    return out


def run_one(doc: dict) -> tuple[IntegrityReport, list[str]]:
    """Return (report, failures) where failures compares to doc['expected']."""
    transcript = from_raw(doc["raw"])
    contradictions, coverage = find_contradictions(transcript)
    report = assemble(coverage, contradictions)

    expected = doc["expected"]["contradictions"]
    got = [
        {"conflict_type": c.conflict_type, "turn_a": c.turn_a, "turn_b": c.turn_b}
        for c in contradictions
    ]
    failures = [] if got == expected else [f"expected {expected}, got {got}"]
    return report, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=None, help="print rendered report for fixture id")
    args = ap.parse_args()

    total_failures = 0
    for doc in load_fixtures():
        fid = doc["fixture"]["id"]
        report, failures = run_one(doc)
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {fid:02d} {doc['fixture']['name']:32s} "
              f"expected: {doc['fixture']['spec_expectation']}")
        for f in failures:
            print(f"         {f}")
        total_failures += len(failures)
        if args.show == fid:
            print()
            print(render(report))
            print()

    print()
    print("all fixtures pass" if not total_failures else f"{total_failures} failure(s)")
    return 1 if total_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
