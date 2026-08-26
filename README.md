# Interview Integrity Check

Reads a finished interview transcript and reports pairs of statements in it
that cannot both be true. That is the whole system.

Output is verbatim quotes and nothing else. There is no score, no risk level,
no confidence number, and no stored field asserting that anyone cheated. A
report is context for a human who is going to talk to the candidate; it is
never a gate.

## Running it

Needs Python 3.9+ and an Anthropic API key.

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # or put it in ~/.zprofile
```

Then point it at a transcript:

```sh
python3 -m integrity path/to/transcript.json
python3 -m integrity path/to/transcript.json --json
```

It also accepts the fixture files directly, which is the fastest way to see
what output looks like:

```sh
python3 -m integrity fixtures/fixture_07_planted_team_size_contradiction.json
```

### Transcript format

Speaker labels, turn ids, and text. Nothing else is required.

```json
{
  "interview_id": "int-2026-0412",
  "candidate_id": "cand-88",
  "turns": [
    {"turn_id": "q1", "speaker": "agent",     "text": "Tell me about the migration."},
    {"turn_id": "a1", "speaker": "candidate", "text": "I led a team of four..."}
  ]
}
```

`question_bucket` (`factual` / `experiential` / `open_ended`) and timestamps are
accepted if present and ignored if not. Adapting to a different transcript
shape is an edit to `integrity/adapters/transcript.py` and nothing else.

### From Python

```python
from integrity.adapters.transcript import from_raw
from integrity.analyze import analyze
from integrity.render import render

report = analyze(from_raw(raw_dict))
print(render(report))
for c in report.contradictions:
    ...
```

`analyze()` returns an `IntegrityReport` with exactly two fields:
`contradictions` and `coverage_note`. An empty list is the normal result.

## Checking it still works

```sh
python3 -m unittest discover -s tests      # 21 tests, no network, no API key
python3 tools/run_fixtures.py              # all 11 fixtures, live, costs money
python3 tools/verifier_probe.py            # 9 pairs the verifier must refuse
python3 tools/blind_review.py              # rate findings without labels
```

Set `INTEGRITY_LLM_CACHE_DIR=$PWD/.llm_cache` to make repeated live runs free
and deterministic. Delete the directory to force fresh sampling.

## How the detector works

Three stages, and two of them exist to say no:

1. **Extract** — the model proposes pairs of statements that conflict, quoting
   both verbatim.
2. **Deterministic filters** — a proposal is dropped if either quote is not a
   literal substring of the turn it claims to come from, if both quotes are
   from the same turn, if the turn is not a candidate answer, if the conflict
   type is not one of the seven in the contract, or if the second quote is
   preceded by a correction marker ("sorry", "actually", "I mean"). None of
   these involve the model.
3. **Verify** — a second call gets only the two quotes and must argue that no
   reasonable reading reconciles them. Anything short of that is dropped.

Ten of the eleven fixtures expect an empty result. That ratio is the point: the
metric this system is tuned against is false positives, not recall. A fabricated
finding costs a real person a job.

## Why there is no timing analysis

An earlier version measured how long each candidate took to answer, comparing
each person only to their own median within a question type. It was removed on
2026-08-24.

If timing is ever revisited, the two constraints that made the old version
defensible still hold, and re-deriving them would be the expensive part:

- **Never compare a candidate to a population.** Absolute latency thresholds
  are a proxy for national origin and for disability. Every comparison must be
  within one person.
- **Normalize by question type before comparing.** Otherwise the detector
  finds the hardest question, which every candidate answers slowly.

The removed code is **not** recoverable — this directory was never under
version control when the deletion happened. `integrity/timing.py` and
`tests/test_negative_controls.py` are gone. Reviving timing means rewriting
them against the two constraints above, not restoring a file.

## What this does not do

- It does not detect cheating. It detects self-inconsistency, most of which is
  ordinary human imprecision.
- It does not look at audio, video, screen contents, keystrokes, or anything
  outside the transcript text.
- It does not compare a candidate to any other candidate, ever.
- It does not run during an interview and cannot influence one.
- An empty report is not a clean bill of health. Anyone who stays consistent
  defeats it, which includes anyone reading from a script.

## Layout

| Path | What it is |
|---|---|
| `integrity/contract.py` | Frozen data types. Scope limits are enforced here, not by memory. |
| `integrity/contradictions.py` | The three-stage pipeline. |
| `integrity/prompts.py` | Extract and verify prompts. Most of both is about when *not* to fire. |
| `integrity/question_pool.py` | Phase 2. Randomized questions so answer banks cannot form. |
| `integrity/adapters/` | The two seams: transcript format and LLM provider. |
| `fixtures/` | 11 frozen transcripts with pre-committed expected output. |
| `tools/` | Fixture runner, verbatim checker, blind review, verifier probe. |
