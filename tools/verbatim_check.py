#!/usr/bin/env python3
"""Assert every quoted span in a report appears exactly in the transcript.

Twenty lines that fully replace a human reader for quote fidelity, and they
catch the worst failure this system can have: showing a recruiter a quote the
candidate never said.
"""

from __future__ import annotations


def verbatim_failures(report, transcript) -> list[str]:
    answers = {e.answer.turn_id: e.answer.text for e in transcript.exchanges if e.answer}
    failures: list[str] = []

    for c in report.contradictions:
        for turn, quote, label in ((c.turn_a, c.statement_a, "a"), (c.turn_b, c.statement_b, "b")):
            if turn not in answers:
                failures.append(f"contradiction statement_{label}: turn {turn} is not an answer turn")
            elif quote not in answers[turn]:
                failures.append(f"contradiction statement_{label}: quote absent from turn {turn}")
    return failures
