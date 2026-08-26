"""The integration surface. One public function.

    analyze(transcript) -> IntegrityReport

Runs after the interview. No latency constraint. Contradiction analysis calls
out to an LLM; if no provider is configured the report says so in its coverage
note rather than failing.
"""

from __future__ import annotations

from .contract import IntegrityReport, Transcript

STANDING_CAVEAT = (
    "Absence of findings is not evidence of integrity. A candidate who is "
    "careful to stay consistent defeats this check. Every finding here has "
    "innocent explanations and is context for a human, never a gate."
)


def assemble(coverage, contradictions) -> IntegrityReport:
    """Build the report. The single place a report is constructed.

    Both analyze() and the fixture runner go through here, so the standing
    caveat cannot be present on one path and missing on the other.
    """
    return IntegrityReport(
        contradictions=contradictions,
        coverage_note="\n".join(list(coverage) + [STANDING_CAVEAT]),
    )


def analyze(transcript: Transcript) -> IntegrityReport:
    from .contradictions import find_contradictions

    contradictions, coverage = find_contradictions(transcript)
    return assemble(coverage, contradictions)
