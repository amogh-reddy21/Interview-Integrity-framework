# Integration

## What we need from the interview platform

Nothing they do not already have. Speaker labels, turn ids, and text:

```json
{
  "interview_id": "int-2026-0412",
  "candidate_id": "cand-88",
  "turns": [
    {"turn_id": "q4", "speaker": "agent",     "text": "...", "question_bucket": "experiential"},
    {"turn_id": "a4", "speaker": "candidate", "text": "..."}
  ]
}
```

Timestamps (`start_ts` / `end_ts`) are accepted and carried through if present,
but nothing reads them. **There is no longer an ask outstanding with the
platform team** — the earlier request for question-end and answer-start
timestamps existed only to support response-latency analysis, which was removed
on 2026-08-24. If that ever comes back, the ask is in git history here.

`question_bucket` is optional. If absent, the adapter resolves it from
`integrity/questions.json` by `question_id`, then by exact question text. If it
still cannot resolve, the bucket is left unset. Buckets describe how an
interview is composed; no finding depends on one, so an unresolved bucket costs
nothing.

## Surface

```python
from integrity.adapters.transcript import from_raw
from integrity.analyze import analyze
from integrity.render import render

report = analyze(from_raw(their_payload))
print(render(report))
```

`analyze()` runs after the interview. No latency constraint. It returns an
`IntegrityReport` with two fields, `contradictions` and `coverage_note`, and an
empty `contradictions` list is the normal result.

Or from a shell, against a transcript file:

```sh
python3 -m integrity transcript.json
python3 -m integrity transcript.json --json
```

## Files that change on integration

| File | Change |
|---|---|
| `integrity/adapters/transcript.py` | Field names and speaker labels. The only file that should need edits. |
| `integrity/adapters/llm.py` | Only if the provider or model changes. |
| `integrity/questions.json` | Their live question pool, if they keep their own. |

Nothing else touches an external format or a provider SDK.

## Question selection

If the agent should draw questions from the randomized pool:

```python
from integrity.question_pool import select_for_interview, selection_log_line, check_counts

questions = select_for_interview(interview_id)     # 4 per bucket, randomized
log.write(selection_log_line(interview_id, questions) + "\n")
for warning in check_counts():                     # buckets this design omits
    log.warning(warning)
```

Log the selection. Rotation needs per-question age (`rotation_report()`), and a
question that leaks can only be retired if you know who was asked it.

## Credentials

`integrity/adapters/llm.py` resolves credentials the normal way — an
`ANTHROPIC_API_KEY` environment variable, or an `ant auth login` profile. With
neither, `analyze()` returns an empty report whose coverage note records that
the analysis did not run, rather than raising. A missing key must never look
like a clean interview, which is why the coverage note is on every report and
is the first thing the renderer prints after the findings.

Set `INTEGRITY_LLM_CACHE_DIR` to cache responses by prompt hash. Required for
repeatable fixture runs while iterating on prompts; leave it unset in
production.

## Before this touches a real candidate

Unchanged by the removal of timing, and still open:

- Confirm with counsel that the existing AI-interview notice covers this
  analysis (Illinois notice requirements, Colorado SB 26-189's adverse-outcome
  explanation and human-review duty).
- Decide, in writing, that a finding never gates a candidate.
- Decide retention: these reports should live as ordinary interview notes with
  the same deletion schedule, not in a separate store.
