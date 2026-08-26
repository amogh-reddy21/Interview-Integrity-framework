"""Data contract for the interview integrity check.

FROZEN. Written before any detector code. Two rules are baked into the types
themselves rather than left to the detectors:

1. Every quoted field is verbatim from the transcript. Never paraphrased.
   Enforced at runtime by tools/verbatim_check.py.
2. No score, level, count summary, composite, or aggregate anywhere in the
   schema. Enforced by tests/test_contract_frozen.py, which walks the field
   names of every dataclass in this module.

Empty lists are the expected output for a clean interview, and a success case.

Timestamps are optional and unused. Response-latency analysis was removed
deliberately: see README.md. The timestamp fields remain on the turn types
because transcripts carry them and dropping them would lose information the
adapter has no business discarding -- nothing reads them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

QuestionBucket = Literal["factual", "experiential", "open_ended"]

BUCKETS: tuple[str, ...] = ("factual", "experiential", "open_ended")


# --------------------------------------------------------------------------
# Input side. Produced only by adapters/transcript.py.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionTurn:
    """A question the agent asked."""

    turn_id: str
    text: str
    bucket: Optional[str] = None
    question_id: Optional[str] = None
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None


@dataclass(frozen=True)
class AnswerTurn:
    """A candidate answer."""

    turn_id: str
    text: str
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None


@dataclass(frozen=True)
class Exchange:
    """One question and the answer to it. answer is None if none was given."""

    question: QuestionTurn
    answer: Optional[AnswerTurn] = None


@dataclass(frozen=True)
class Transcript:
    interview_id: str
    exchanges: tuple[Exchange, ...] = ()
    candidate_id: Optional[str] = None
    source: Optional[str] = None


# --------------------------------------------------------------------------
# Output side.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Contradiction:
    """Two statements in one transcript that cannot both be true."""

    statement_a: str  # verbatim
    statement_b: str  # verbatim
    turn_a: str
    turn_b: str
    conflict_type: Literal[
        "team_size",
        "ownership",
        "timeline",
        "scope",
        "technology",
        "role",
        "quantified_outcome",
    ]
    explanation: str  # one sentence naming the conflict


@dataclass(frozen=True)
class IntegrityReport:
    contradictions: list[Contradiction] = field(default_factory=list)
    coverage_note: str = ""
