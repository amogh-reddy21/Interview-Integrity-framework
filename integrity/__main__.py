"""Command-line entry point.

    python3 -m integrity <transcript.json>

Reads one transcript, runs the check, prints the report. Needs ANTHROPIC_API_KEY
in the environment. Exit status is 0 whether or not anything was found -- a
finding is not an error, and nothing here is a pass/fail gate on a person.
"""

from __future__ import annotations

import argparse
import json
import sys

from .adapters.transcript import from_raw
from .analyze import analyze
from .render import render


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="integrity", description=__doc__)
    ap.add_argument("transcript", help="path to a transcript JSON file")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    with open(args.transcript) as f:
        doc = json.load(f)

    # Fixture files wrap the transcript in a "raw" key; plain transcripts do not.
    raw = doc["raw"] if "raw" in doc and "turns" not in doc else doc

    try:
        report = analyze(from_raw(raw))
    except ValueError as exc:
        print(f"cannot read transcript: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "contradictions": [vars(c) for c in report.contradictions],
            "coverage_note": report.coverage_note,
        }, indent=2))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
