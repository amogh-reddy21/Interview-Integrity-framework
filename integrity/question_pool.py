"""Phase 2 -- randomized question pool.

Prevention rather than detection, and it has to exist before either detector
ships. An agent that asks the same eight questions every interview creates the
leak that memorized answer banks are built from.

Two constraints shape the selection:

* Randomize *which* questions, but fix *how many* per bucket, so every
  candidate gets the same shape of interview even though no two get the same
  questions. Varying the mix between candidates would make their transcripts
  incomparable for any human reading them side by side.
* Log the selection. Rotation needs per-question age, and a question that has
  leaked can only be retired if you know who was asked it.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from .contract import BUCKETS

POOL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.json")


@dataclass(frozen=True)
class PooledQuestion:
    question_id: str
    bucket: str
    text: str
    added: str
    retired: Optional[str] = None

    def age_days(self, as_of: Optional[date] = None) -> int:
        as_of = as_of or date.today()
        return (as_of - datetime.strptime(self.added, "%Y-%m-%d").date()).days


def _load() -> dict:
    with open(POOL_PATH) as f:
        return json.load(f)


def load_pool(include_retired: bool = False) -> list[PooledQuestion]:
    doc = _load()
    out = [
        PooledQuestion(
            question_id=q["question_id"],
            bucket=q["bucket"],
            text=q["text"],
            added=q["added"],
            retired=q.get("retired"),
        )
        for q in doc["questions"]
    ]
    if not include_retired:
        out = [q for q in out if q.retired is None]
    return out


def per_interview_counts() -> dict[str, int]:
    return dict(_load()["per_interview_counts"])


def select_for_interview(
    interview_id: str,
    counts: Optional[dict[str, int]] = None,
    seed: Optional[int] = None,
) -> list[PooledQuestion]:
    """Pick a randomized set with a fixed count per bucket.

    seed is for reproducing a selection in a test, not for production use.
    """
    counts = counts or per_interview_counts()
    rng = random.Random(seed if seed is not None else f"{interview_id}:{os.urandom(8)!r}")
    pool = load_pool()

    selected: list[PooledQuestion] = []
    for bucket in BUCKETS:
        want = counts.get(bucket, 0)
        if want == 0:
            continue
        available = [q for q in pool if q.bucket == bucket]
        if len(available) < want:
            raise ValueError(
                f"pool has {len(available)} live {bucket} question(s), need {want}"
            )
        selected.extend(rng.sample(available, want))

    rng.shuffle(selected)
    return selected


def check_counts(counts: Optional[dict[str, int]] = None) -> list[str]:
    """Report buckets that this interview design leaves out.

    Not an error -- deciding to ask no open-ended questions is a legitimate
    design choice. But it should be recorded, so that a later reader knows the
    interview never covered that ground rather than assuming it did.
    """
    counts = counts or per_interview_counts()
    warnings = []
    for bucket in BUCKETS:
        if counts.get(bucket, 0) == 0:
            warnings.append(f"{bucket}: not asked in this interview design")
    return warnings


def bucket_for(question_id: Optional[str], text: str = "") -> Optional[str]:
    """Resolve a bucket for a transcript question. Never guessed from wording.

    Retired questions are included: an old transcript still needs its buckets.
    """
    pool = load_pool(include_retired=True)
    if question_id:
        for q in pool:
            if q.question_id == question_id:
                return q.bucket
    if text:
        normalized = " ".join(text.split()).strip().lower()
        for q in pool:
            if " ".join(q.text.split()).strip().lower() == normalized:
                return q.bucket
    return None


def rotation_report(as_of: Optional[date] = None) -> dict:
    """Per-question age and what is due for rotation."""
    doc = _load()
    max_age = int(doc.get("rotation_max_age_days", 90))
    live = load_pool()
    stale = [q for q in live if q.age_days(as_of) > max_age]
    by_bucket = {b: len([q for q in live if q.bucket == b]) for b in BUCKETS}
    return {
        "live_questions": len(live),
        "live_by_bucket": by_bucket,
        "rotation_max_age_days": max_age,
        "due_for_rotation": [
            {"question_id": q.question_id, "bucket": q.bucket, "age_days": q.age_days(as_of)}
            for q in sorted(stale, key=lambda q: q.age_days(as_of), reverse=True)
        ],
    }


def selection_log_line(interview_id: str, questions: Iterable[PooledQuestion]) -> str:
    """One JSONL line recording what this candidate was actually asked."""
    return json.dumps(
        {
            "interview_id": interview_id,
            "asked": [
                {"question_id": q.question_id, "bucket": q.bucket, "added": q.added}
                for q in questions
            ],
        },
        sort_keys=True,
    )
