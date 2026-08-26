# Code walkthrough

For someone opening this repo for the first time. Read in this order; the whole
system is ~1,000 lines of actual logic.

## One sentence

It reads a finished interview transcript and prints pairs of things the
candidate said that cannot both be true, quoted word for word — nothing else.

## What is detected

Only one thing: **self-contradiction between two different answers by the same
candidate in the same interview**. Seven categories, and the list is closed —
anything outside it is thrown away in code, not left to the model's judgement:

| Type | Conflict about |
|---|---|
| `team_size` | how many people were involved |
| `ownership` | who did the work / who was responsible |
| `timeline` | when it happened, how long it took |
| `scope` | what the work included |
| `technology` | what tools or systems were used |
| `role` | seniority, title, function |
| `quantified_outcome` | a number claimed as a result |

There is no timing analysis, no audio, no video, no keystrokes, no comparison
against other candidates, and no score. `IntegrityReport` has exactly two
fields — `contradictions` and `coverage_note` — and a test fails the build if a
field named anything like `score`, `risk`, `confidence`, or `verdict` ever
appears in the contract.

## What is deliberately NOT detected

Most of the prompt text in `integrity/prompts.py` is this list, because firing
on any of it is the failure mode that matters:

self-correction · rephrasing · added detail or clarification · approximation
("around a hundred" vs "a hundred and twelve") · two different projects or
periods · owning something while other people also touched it · disfluency and
non-native phrasing · changing an opinion.

## The path a transcript takes

```
transcript.json
  → adapters/transcript.py   from_raw()   turns → (question, answer) Exchanges
  → analyze.py               analyze()
      → contradictions.py    find_contradictions()
            stage 1  EXTRACT   one LLM call over the whole transcript
            stage 2  FILTER    _structural_reject(), pure Python, no model
            stage 3  VERIFY    one LLM call per survivor, in isolation
      → assemble()           attaches the standing caveat
  → render.py                plain text, or --json from __main__.py
```

### Stage 1 — extract (`prompts.EXTRACT`)

One call sends the rendered transcript and asks for pairs of conflicting
statements, each quoted verbatim, with turn ids and a conflict type. The reply
is constrained by `EXTRACT_SCHEMA` (JSON schema), so shape is guaranteed;
truthfulness is not, which is what stage 2 is for. The expected answer is an
empty list.

### Stage 2 — deterministic filters ([contradictions.py:133](integrity/contradictions.py#L133))

No model involved, so these cannot regress when a prompt is edited. A proposal
is dropped if:

1. any required field is missing;
2. `conflict_type` is not one of the seven;
3. `turn_a == turn_b` — both quotes from one answer is a person correcting
   themselves mid-sentence, not two conflicting claims;
4. a cited turn is not a candidate answer (kills quotes attributed to the
   interviewer);
5. **a quote is not a literal substring of the answer it claims to come from** —
   this is the one that catches invented or "cleaned up" quotes;
6. a correction marker ("sorry", "actually", "I mean", "no, wait", …) appears in
   the 40 characters immediately before a quote. Only immediately before — a
   "sorry" elsewhere in a long answer says nothing about this sentence.

### Stage 3 — verify (`prompts.VERIFY`)

Each survivor goes to a *second, separate* call that sees only the two quotes
and their two source answers — not the rest of the interview, not the earlier
reasoning. It answers one boolean: `both_can_be_true`. The burden of proof sits
on the detector; anything short of "no reasonable reading reconciles these" is
dropped. Errors, unparseable output, and a missing API key all resolve to
*drop*, never to *keep*.

Every drop, from either stage, is written into the coverage note, so the report
says what was suppressed and why.

## Output

`render()` prints the surviving pairs under "Things to look into" (never
"flags"), then the coverage note, then a fixed "How to read this" block. The
standing caveat is attached in one place, `analyze.assemble()`, so it cannot go
missing on one code path.

An empty report is the normal, expected result — and means nothing was
measured, not that the interview was clean.

## Failure behaviour

No API key, a client that will not construct, a safety refusal, or bad JSON all
produce an **empty report with a coverage note explaining that the analysis did
not run**. A missing key must never look like a clean interview.

## The two seams

Everything else is provider- and format-agnostic:

- [integrity/adapters/transcript.py](integrity/adapters/transcript.py) — the only file that changes for a new
  transcript format.
- [integrity/adapters/llm.py](integrity/adapters/llm.py) — the only file that touches a provider SDK.
  Also does prompt-hash disk caching when `INTEGRITY_LLM_CACHE_DIR` is set,
  which is what makes fixture runs free and repeatable.

## Files, in reading order

| File | Why you would open it |
|---|---|
| [integrity/contract.py](integrity/contract.py) | The data types. Start here — the scope limits are in the type definitions. |
| [integrity/contradictions.py](integrity/contradictions.py) | The three stages. The whole detector. |
| [integrity/prompts.py](integrity/prompts.py) | What the model is told, mostly about when not to fire. |
| [integrity/analyze.py](integrity/analyze.py) | 37 lines. The public entry point. |
| [integrity/render.py](integrity/render.py) | Text output and the limitations block. |
| [integrity/adapters/](integrity/adapters/) | The two seams above. |
| [integrity/question_pool.py](integrity/question_pool.py) | Unrelated to detection — randomized question selection so answer banks cannot form. |
| [fixtures/](fixtures/) | 11 frozen transcripts with expectations committed before the detector existed. 10 of 11 expect silence. |
| [tests/](tests/) | 21 offline tests: filters (stubbed model), frozen contract, frozen fixture hashes. |
| [tools/](tools/) | Live fixture runner, verbatim checker, verifier probe, blind review. |

## Seeing it work

```sh
source .venv/bin/activate
export INTEGRITY_LLM_CACHE_DIR=$PWD/.llm_cache        # free, uses cached replies

python3 -m integrity fixtures/fixture_07_planted_team_size_contradiction.json  # fires
python3 -m integrity fixtures/fixture_08_self_correction.json                  # silent
python3 -m unittest discover -s tests                 # 21 tests, no network
```

Fixture 07 is the demo case: turn `a2` says "I led a team of four on the
migration", turn `a8` says "it was mostly just me… I did not really have help".
Same project, same period, both quotes returned verbatim.

## Why it is built this way

Ten of eleven fixtures expect an empty result. The metric this system is tuned
against is false positives, not recall — a fabricated finding costs a real
person a job. Two of the three stages exist only to say no, and the one that
cannot be weakened by a prompt edit is the middle one, written in plain Python.

The honest limit: this finds invented stories that fall apart under follow-up
questions. Someone reading from an AI assistant produces a *more* consistent
transcript than an honest nervous person, and this system will never see them.
