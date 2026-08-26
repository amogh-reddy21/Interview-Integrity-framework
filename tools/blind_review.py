#!/usr/bin/env python3
"""Blind review harness.

Substitutes for the second reader you do not have. Findings are shuffled and
stripped of every fixture label, so you rate each one without knowing which
fixture produced it and without the "oh, that's fixture 3, it's supposed to
fire" reflex. Rate first, then unshuffle with --key.

Usage:
  python3 tools/blind_review.py                 # print shuffled findings
  python3 tools/blind_review.py --key <run_id>  # reveal the mapping afterwards
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_fixtures import load_fixtures, run_one  # noqa: E402

KEY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".blind_keys")


def collect() -> list[dict]:
    items = []
    for doc in load_fixtures():
        report, _ = run_one(doc)
        for c in report.contradictions:
            items.append({
                "kind": "contradiction",
                "source_fixture": doc["fixture"]["id"],
                "text": (
                    f"{c.conflict_type}\n"
                    f"    {c.turn_a}: \"{c.statement_a}\"\n"
                    f"    {c.turn_b}: \"{c.statement_b}\"\n"
                    f"    {c.explanation}"
                ),
            })
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=None, help="reveal the mapping for a run id")
    args = ap.parse_args()

    os.makedirs(KEY_DIR, exist_ok=True)

    if args.key:
        path = os.path.join(KEY_DIR, f"{args.key}.json")
        with open(path) as f:
            key = json.load(f)
        print(f"run {args.key}")
        for entry in key["items"]:
            print(f"  #{entry['n']}: fixture {entry['source_fixture']} ({entry['kind']})")
        return 0

    items = collect()
    random.shuffle(items)
    run_id = time.strftime("%Y%m%d-%H%M%S")

    print(f"Blind review run {run_id} -- {len(items)} finding(s)")
    print("Rate each one before looking at the key: is this something a")
    print("recruiter should look into, or is it noise about a real person?")
    print()
    for n, item in enumerate(items, start=1):
        print(f"#{n}")
        print(item["text"])
        print()

    with open(os.path.join(KEY_DIR, f"{run_id}.json"), "w") as f:
        json.dump(
            {"items": [
                {"n": n, "kind": i["kind"], "source_fixture": i["source_fixture"]}
                for n, i in enumerate(items, start=1)
            ]},
            f,
            indent=2,
        )
    print(f"Key saved. Reveal with: python3 tools/blind_review.py --key {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
