"""Plain-text rendering of a report. Verbatim quotes only.

Framing is deliberate: "things to look into", never "flags". Findings are
unconfirmed by construction, and the report must never read as a clean bill of
health.
"""

from __future__ import annotations

from .contract import IntegrityReport

HEADER = "Things to look into"
LIMITATIONS = (
    "How to read this",
    (
        "- Nothing here is a finding of cheating. Each item is a pair of "
        "quotes with an innocent explanation available.",
        "- A contradiction can be imprecise phrasing, a misremembered detail, "
        "or two things that sound incompatible but are not. Read both quotes "
        "in full before drawing anything from them.",
        "- An empty report means nothing was measured, not that the interview "
        "was clean. A candidate who stays consistent defeats this check.",
        "- Ask the candidate about it. A contradiction a person can explain in "
        "one sentence was never evidence of anything.",
    ),
)


def render(report: IntegrityReport) -> str:
    out: list[str] = [HEADER, "=" * len(HEADER), ""]

    if not report.contradictions:
        out.append("No contradictions were measured.")
        out.append("")
    else:
        for c in report.contradictions:
            out.append(f"{c.turn_a} vs {c.turn_b} -- {c.conflict_type}")
            out.append(f"    {c.turn_a}: \"{c.statement_a}\"")
            out.append(f"    {c.turn_b}: \"{c.statement_b}\"")
            out.append(f"    {c.explanation}")
            out.append("")

    out.append("Coverage")
    for line in report.coverage_note.splitlines():
        out.append(f"    {line}")
    out.append("")

    title, bullets = LIMITATIONS
    out.append(title)
    for bullet in bullets:
        out.append(f"    {bullet}")
    return "\n".join(out)
