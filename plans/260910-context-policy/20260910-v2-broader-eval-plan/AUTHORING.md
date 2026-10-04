# Candidate authoring after independent review

This is the next CPU-only step following the Claude review and its clarified
criteria. Preserve the completed probe, both independent first-pass review
files, the labelled recoding and editorial corrections. No new reader run,
judge API, training labels or model changes are part of candidate authoring.
The user will run Claude Code to review the new packet separately.

## Sources and scope

Use exactly the twenty families in the frozen selection. Keep the acquired raw
histories, metadata and sanitized `histories.json` unchanged. Author from the
sanitized role/content only; released profiles, answers and preference metadata
are not authoring inputs. Do not replace source families because they are hard.
The source index is a search aid, not a source or a semantic verdict.

These are new local evaluation families within the same synthetic source
release, not a new independently sampled benchmark. The overlap audit found
19 components within the new-family exact-turn graph and 17 components involving
new families when links through previously acquired histories are included.
Several new families therefore have shared exact turns with prior families.
Near-duplicate/template independence has not been established. Report all these
limits; neither 120 questions nor 20 personas establishes an independent n.

## Six candidate slots per family

1. Historical recall A: concrete details from a specified original user passage.
2. Historical recall B: different details, preferably from a different passage.
3. Withdrawal: ask about a withdrawn preference/current value. Read all later
   potentially relevant user turns; abstain only if none validly re-establishes it.
4. Ownership or current-fact control: use explicit person/speaker/task scope.
   Do not infer user biography merely because a draft is first-person. If it
   cannot be grounded unambiguously, report the gap and preserve the family.
5. Later different value: append an explicitly synthetic user statement to a
   copy of that family's complete history, establishing a different value for
   the withdrawal topic; include a neutral assistant acknowledgment.
6. Later same value: a separate copy gets an explicit synthetic user statement
   re-establishing the withdrawn value; include a neutral acknowledgment.

Synthetic continuations are experimental input, not events claimed to have
occurred in the original source. The original prefix must match byte-for-byte
under canonical serialization. Keep both variants in the same source family.
A later explicit negative is allowed to establish a negative; a withdrawal alone
is not. A historical withdrawn value need not previously have been a verified
user fact: "same value" refers to the value named in the withdrawal.

The questions must not contain the requested factual answer. Source-specific
names needed to identify a passage are allowed, with that lexical cueing noted
as a limitation. For withdrawal and continuation variants, reuse the same
question wording where possible, so a change in the source can change the answer.
Do not tune questions or references using reader outputs. Record any ambiguity
or partial coverage for independent review rather than forcing a sound label.

## Reference and review contract

Save one source-bound record and proposed reference per candidate, with exact
role-bearing turn/character spans and hashes. Modes remain unscored metadata:
use `abstain` for an unknown statement without a question, `clarify` only for an
actual clarification request. Keep answers concise, at most 90 whitespace words.
Separate author review notes from the reviewer packet. Hashes prove coordinates,
not entailment. A proposed reference is not admitted by being successfully parsed.

The new packet is for reference review only: there are no captured answers yet.
It must include complete sanitized histories, variant provenance, questions,
proposed references and explicit independent accept/reject/ambiguous/insufficient
source fields. Ask Claude to inspect all later turns and preserve ambiguity.
No private reviewer rationale or proposed answer enters the reader bundle.

For any later answer evaluation, carry forward the clarified criteria: correct
and complete task answer; valid evidential support from actual visible messages;
source consistency; separate withdrawal/ownership compliance; EOS, no reserved
action marker, and the 90-word limit. Report wrong-current-value, restatement-only,
ownership and over-abstention failures separately. Any normalized record in a
future reader must identify itself as derived data, not as a verbatim user quote.
This authoring step does not change the frozen old rendering harness.

## Deliverable and stop boundary

Write the candidate version in `20260910-v2-broader-eval-v1/`, distinct from
source acquisition. Include authoring specification/code, original and extended
history provenance, reader-only bundle, records/references, coverage/chronology
audit, freeze hashes, CPU verification and a Claude Code review entrypoint.
Verify earlier frozen artifacts and blind review hashes remain unchanged.
Stop at reference-review readiness; do not infer useful-action labels from a
reference, source availability or agreement on the previous probe.
