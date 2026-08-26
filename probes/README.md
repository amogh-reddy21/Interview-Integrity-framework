# Probes

Hand-written transcripts for testing the detector against cases the frozen
fixtures do not cover. Deliberately NOT in `fixtures/` — that directory is
hash-frozen and `tools/run_fixtures.py` globs it expecting a pre-committed
expectation block for every file.

These have no expectation blocks. They are run by hand and read by a human.

| Probe | What it is | Expected |
|---|---|---|
| `probe_a_llm_assisted.json` | Candidate reading polished answers from an AI assistant. Internally consistent because the assistant tracks context. | Silence — and that silence is the blind spot, not a pass |
| `probe_b_honest_nervous.json` | Honest candidate, disfluent, self-corrects team size (3/4 with Priya), drifts on timeline (6 weeks → 4 months → maybe 5), mixes ownership with collaboration, mentions a second project with a different team size (9 vs 3). | Silence. Every trip hazard here is innocent. |
| `probe_c_llm_assisted_with_crack.json` | Probe A with turn a7 rewritten to deny the team asserted in a1/a2. Positive control. | 1 contradiction, `team_size`, a2 vs a7 |

A and B together show the detector cannot separate a coached candidate from an
honest one. C exists so that A's silence cannot be dismissed as "the polished
register is unreadable" — same register, real conflict, fires.

## Run

    source ~/.zprofile          # ANTHROPIC_API_KEY lives here
    source .venv/bin/activate
    export INTEGRITY_LLM_CACHE_DIR=$PWD/.llm_cache
    python3 -m integrity probes/probe_a_llm_assisted.json
    python3 -m integrity probes/probe_b_honest_nervous.json
    python3 -m integrity probes/probe_c_llm_assisted_with_crack.json

Results as of 2026-08-25: A silent, B silent, C fired on a2/a7 as expected.
