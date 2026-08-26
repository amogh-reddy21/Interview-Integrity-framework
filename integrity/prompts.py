"""Prompts for Phase 3. Kept in one file because this is the part that gets
iterated on, and iteration is easier when the text is not buried in logic.

Most of both prompts is about when *not* to fire. That ratio is deliberate: a
contradiction detector that fires on self-corrections is worse than no
contradiction detector, because it teaches recruiters to ignore the whole
report.
"""

EXTRACT = """\
You are examining the transcript of one job interview. Your only task is to \
find pairs of statements *by the candidate* that cannot both be true.

You are not assessing the candidate. You are not judging how articulate, \
specific, confident, or prepared they sound. You are not scoring anything. You \
are looking for factual incompatibility and nothing else.

# What counts as a contradiction

Two statements the candidate made, in DIFFERENT turns, about the SAME thing, \
where accepting one requires rejecting the other. The conflict must be in one \
of these categories:

- team_size: how many people were involved
- ownership: who did the work or who was responsible
- timeline: when something happened or how long it took
- scope: what the work included
- technology: what tools or systems were used
- role: their seniority, title, or function
- quantified_outcome: a number they claim as a result

# What does NOT count. Read this part twice.

Return nothing for any of the following. These are the normal texture of \
honest speech, and firing on them is the worst failure this system can have.

1. SELF-CORRECTION. The candidate revises their own statement, whether inside \
one answer or in a later one. Markers include "sorry", "actually", "no, wait", \
"I mean", "I misspoke", "or rather", "I forgot". "There were four of us, sorry, \
five with the intern" is one corrected fact, not two conflicting ones. The \
corrected version is simply what they said.

2. REPHRASING. The same fact in different words, often because you asked \
several overlapping questions. "I owned the pipeline", "it was mine end to \
end", and "I was the one driving it" are one claim stated three ways.

3. CLARIFICATION OR ADDED DETAIL. A later statement that refines an earlier \
one rather than replacing it. "About six months" then "closer to eight if you \
count the pilot" is one person being precise, not inconsistent.

4. APPROXIMATION. "Around a hundred" and "a hundred and twelve" agree. \
"Roughly two years" and "twenty-six months" agree.

5. DIFFERENT REFERENTS. Two different projects, teams, employers, or periods. \
If you cannot establish that both statements are about the same thing, do not \
fire. Ambiguity is a reason to stay silent, never a reason to fire.

6. OWNERSHIP ALONGSIDE COLLABORATION. "I owned it" is compatible with "other \
people touched it", "two others were secondary on call", and "I had help with \
the frontend". Leading a team is also compatible with personally doing a large \
share of the work. What is NOT compatible is claiming a team and then denying \
that anyone else was involved at all -- "I led a team of four" against "it was \
just me, I had no help on that" is a real conflict, because the second \
statement denies the team exists.

7. DISFLUENCY. Restarts, repetitions, filler, grammatical errors, and \
non-native phrasing are never evidence of anything. A candidate saying "I \
build the, the parser" has not contradicted themselves. Judge only the facts \
asserted.

8. OPINION OR PREFERENCE CHANGING. Saying they like small teams and later \
saying they enjoyed a large project is not a contradiction.

# Output

Return JSON. `contradictions` is usually EMPTY -- most interviews contain \
none, and an empty list is the correct and expected answer. Only include a \
pair you would be willing to show the candidate alongside both quotes.

For each one:
- statement_a / statement_b: the candidate's words, copied EXACTLY from the \
transcript, character for character. Do not clean up, trim, join, or \
paraphrase. Quote a complete sentence or clause, not a fragment.
- turn_a / turn_b: the turn ids the quotes came from. Must be different turns.
- conflict_type: one of the categories above.
- explanation: one sentence naming what conflicts. No speculation about why.

# Transcript

{transcript}
"""

VERIFY = """\
A contradiction detector flagged the two statements below in one interview \
transcript. Your job is to check it, and the burden of proof is on the \
detector.

Answer one question: would a careful reader accept both statements as \
describing the same situation?

Say they CAN both be true when the second is a correction of the first, a \
rephrasing, a clarification or added detail, an approximation, about a \
different project or period, or when the candidate simply spoke loosely. \
Ownership and collaboration coexist: "I owned it" sits fine beside "others \
touched it" or "two others were secondary on call". Doing the majority of the \
work personally sits fine beside leading a team.

Say they CANNOT both be true when accepting one requires rejecting the other \
on the same subject. In particular -- and this is the case verifiers most often \
get wrong -- a claim that other people were involved is NOT compatible with a \
later denial that anyone else was involved. "I led a team of four" against "it \
was mostly just me, I did not really have help" is incompatible: the first \
asserts three other contributors, the second withdraws them. A stated reason \
for their absence ("they were tied up on another project") does not reconcile \
the two -- it explains why the team may not have contributed, which is itself \
in tension with having led a team of four on the work. Someone who led four \
people and did most of the work would say they did most of it, not that they \
had no help.

The burden of proof is on the detector for judgement calls about referents, \
approximation, and phrasing. It is not a licence to reconcile a plain \
inconsistency by inventing circumstances the candidate never described.

Statement A, from turn {turn_a}:
"{statement_a}"

The full answer that quote came from:
{context_a}

Statement B, from turn {turn_b}:
"{statement_b}"

The full answer that quote came from:
{context_b}

The detector called this a {conflict_type} conflict and said: {explanation}

Return JSON with `both_can_be_true` (boolean) and `reason` (one sentence).
"""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement_a": {"type": "string"},
                    "statement_b": {"type": "string"},
                    "turn_a": {"type": "string"},
                    "turn_b": {"type": "string"},
                    "conflict_type": {
                        "type": "string",
                        "enum": [
                            "team_size",
                            "ownership",
                            "timeline",
                            "scope",
                            "technology",
                            "role",
                            "quantified_outcome",
                        ],
                    },
                    "explanation": {"type": "string"},
                },
                "required": [
                    "statement_a",
                    "statement_b",
                    "turn_a",
                    "turn_b",
                    "conflict_type",
                    "explanation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["contradictions"],
    "additionalProperties": False,
}

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "both_can_be_true": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["both_can_be_true", "reason"],
    "additionalProperties": False,
}
