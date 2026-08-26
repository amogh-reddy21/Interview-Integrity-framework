#!/usr/bin/env python3
"""Probe the verification pass directly with pairs it should refuse.

The fixture suite only exercises the verifier on pairs that extraction
proposed. When extraction is doing its job, the verifier is never tested at
all -- so a change that loosens it can pass the whole suite while quietly
removing the second line of defence.

Every pair below is a real quote pair from a false-positive fixture, chosen
because a trigger-happy extractor could plausibly propose it. The verifier must
say both statements can be true for every one of them.

Usage: .venv/bin/python tools/verifier_probe.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrity.contradictions import _verify  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (fixture, turn_a, quote_a, turn_b, quote_b, conflict_type, explanation, why it must be refused)
PROBES = [
    (8, "a2", "There were four of us on it", "a8",
     "we shipped it with two people less than the original plan asked for",
     "team_size", "four people versus a reduced headcount",
     "a plan's headcount and the actual team are different quantities"),
    (8, "a2", "There were four of us on it", "a6",
     "I wrote the ingestion layer and reviewed most of the rest",
     "ownership", "a team of four versus doing the work personally",
     "leading four people is compatible with writing a component yourself"),
    (8, "a3", "About six months.", "a7", "About twelve thousand monthly.",
     "timeline", "inconsistent figures",
     "different quantities entirely; the extractor would be pattern-matching numbers"),
    (9, "a1", "I owned the ingestion pipeline.", "a3",
     "Other people touched it, but I was the one driving that pipeline.",
     "ownership", "sole ownership versus others involved",
     "ownership coexists with others touching the code"),
    (9, "a1", "I owned the ingestion pipeline.", "a7",
     "Two others were secondary, but in practice it came to me.",
     "ownership", "sole ownership versus a shared rotation",
     "being primary on call is compatible with secondaries existing"),
    (10, "a4", "for two months we have wrong data and nobody see it", "a5",
     "A person in finance, she notice the totals are not matching",
     "timeline", "nobody noticed versus somebody noticed",
     "nobody saw it *during* those two months; she is how it was eventually found"),
    (10, "a3", "Three. Me and two, ah, two others.", "a6",
     "we go back and, ah, reprocess everything from before",
     "team_size", "team size versus the work described",
     "unrelated statements; disfluency is not evidence"),
    (11, "a2", "I was one of three engineers on it", "a10",
     "Around sixty engineers when I left, maybe forty when I joined.",
     "team_size", "three engineers versus sixty",
     "different referents: one project team versus the whole engineering org"),
    (11, "a2", "I owned the change-data-capture piece specifically", "a4",
     "Convincing people the numbers were right.",
     "ownership", "owning a component versus a collaborative problem",
     "not in tension at all"),
]


def answers_for(fixture_id: int) -> dict[str, str]:
    path = glob.glob(os.path.join(ROOT, "fixtures", f"fixture_{fixture_id:02d}_*.json"))[0]
    with open(path) as f:
        doc = json.load(f)
    return {t["turn_id"]: t["text"] for t in doc["raw"]["turns"] if t["speaker"] == "candidate"}


def main() -> int:
    failures = 0
    for fid, turn_a, quote_a, turn_b, quote_b, ctype, explanation, why in PROBES:
        answers = answers_for(fid)
        for turn, quote in ((turn_a, quote_a), (turn_b, quote_b)):
            if quote not in answers.get(turn, ""):
                print(f"[SETUP ERROR] fixture {fid} {turn}: probe quote is not verbatim")
                return 2

        item = {
            "statement_a": quote_a, "statement_b": quote_b,
            "turn_a": turn_a, "turn_b": turn_b,
            "conflict_type": ctype, "explanation": explanation,
        }
        verdict = _verify(item, answers)
        refused = verdict is not None
        status = "REFUSED" if refused else "!! ACCEPTED !!"
        print(f"[{status}] fixture {fid} {turn_a}/{turn_b} ({ctype})")
        print(f"          should be refused because: {why}")
        if refused:
            print(f"          verifier said: {verdict.split(': ', 1)[-1][:200]}")
        else:
            failures += 1
        print()

    print(f"{len(PROBES) - failures}/{len(PROBES)} refused")
    if failures:
        print(f"{failures} probe(s) got through the verifier -- it is too permissive")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
