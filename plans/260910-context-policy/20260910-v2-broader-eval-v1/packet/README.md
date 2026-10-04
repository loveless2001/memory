# Independent reference review: 120 candidates

Review every question and proposed reference. No model answers have been
generated for this candidate. Independence here means a separate reviewer from
the source-only author, not independent data, independent human judgment, or
blinding to the proposed answers.

## Inputs

- `cases.jsonl`: 120 question/reference records with source bindings and spans.
- `histories/F001.md` through `histories/F020.md`: complete sanitized original
  histories with zero-based role-bearing turns. Read each in full.
- `variants.json`: forty synthetic extensions. Each consists of its complete
  base history followed by the two specified messages. The first appended turn
  is `base_turns`; the assistant acknowledgment is `base_turns + 1`.
- `../review-template.json`: output schema, with all case IDs and bindings.
- `../freeze.json`: the fixed candidate inputs; bind the review to this file's
  SHA-256, printed by `verify.py`.

The packet does not contain hidden persona profiles, released benchmark
answers, prior model outputs or prior author verdicts. Do not inspect raw source
JSON, private authoring notes/specifications, old judge outputs or older result
reports to decide these references. The full sanitized histories and synthetic
extensions contain the allowed source evidence. The validator can hash other
files for integrity without their contents becoming review inputs.

## What to decide

For each case independently, use one status:

| Status | Meaning |
| --- | --- |
| `accept` | The question is answerable at its stated scope and the proposed reference is correct and complete as written. |
| `reject` | There is a definite question/reference error. Explain it and optionally propose a corrected answer. |
| `ambiguous` | More than one materially different interpretation remains plausible. Preserve the ambiguity. |
| `insufficient_source` | The supplied material is incomplete or cannot support deciding the proposed reference. |

An intentionally correct unknown answer can be accepted; it is not automatically
`insufficient_source`. For such an answer, read all later user turns for a valid
re-establishment and explain why relevant later text does or does not establish
the requested value. A keyword scan is a search aid, not the semantic decision.
Do not infer a preference merely from a topical question. Conversely, a question
can contain an explicit personal assertion; inspect its actual wording.

An explicit request to forget a preference makes that value unavailable for
current personalization. It does not establish its opposite. A later explicit
user statement may establish a value, including the same value or an explicit
negative. An assistant's repetition cannot establish a user fact. For a query
about the current value, an unknown answer should not unnecessarily repeat the
withdrawn value while explaining the withdrawal.

Historical questions deliberately ask about the text of an identified original
passage. Answer at that historical textual scope. Do not turn a first-person
editing or translation passage into current user biography, and do not declare
every first-person draft fictional. Sender, recipient, narrator, named third
party, and current user are distinct evidential roles. For references with
`ownership: quoted_text_only`, `current_status: current` means the quotation is
valid source evidence for the scoped question, not that its contents are current
user facts. This inherited schema convention makes no claim about the narrator's
current circumstances.

The forty continuations are synthetic experimental inputs. They are not events
reported by the original dataset. Apply them after the complete original
history, preserving chronology. A synthetic current declaration is an allowed
source for its own variant; it is absent from the base and the other variant.

Check that each question specifies what it asks for without supplying the
requested answer, and that each reference answers at that granularity. Do not
accept a true but incomplete answer. Flag ambiguous passage identification,
unsupported specificity, missing components, or inadvertent answer leakage.
References must be at most 90 whitespace-separated words. Mode is unscored
metadata: `abstain` describes an unknown answer without a question; `clarify`
requires an actual clarification request. There are no generated bodies here,
so EOS or generation-format behavior cannot be evaluated in this review.

## Output and evidence

Create `../review/` and copy the template there as `reference-review.json`.
Supply the actual reviewer identity/model, ISO timestamp, and candidate freeze
hash. List the twenty family IDs in `full_base_histories_read` only after reading
the complete base histories. Complete all 120 statuses and case-specific
rationales. If review must span sessions, keep unfinished work explicitly
`pending`; do not claim a completed review until all source reads and decisions
are done.

For each accepted case, give at least one supporting source span. Use the exact
span schema from the proposed references: `turn`, `role`, `start`, `end`, and
`text_sha256`. Offsets count Python Unicode characters in the original message
content, excluding the Markdown turn header. The hash covers only the selected
UTF-8 substring. Existing spans can be reused only after inspecting them.
Contradictory spans are encouraged for rejected or ambiguous cases. For variants,
all evidence coordinates refer to the complete base-plus-extension history.
Do not put a corrected answer into an `accept` record; use `reject` if correction
is necessary. A `suggested_answer` is a proposal and does not modify the source.

Run the validation command in the repository entrypoint. It checks coverage,
source bindings and schema, not whether the reviewer reasoning is sound. Keep
the candidate files unchanged; a later revision must be separately frozen.

## Limits to carry forward

These are twenty reserved families from the same synthetic PersonaMem-v2 training
release, with six related questions per family. Forty are synthetic continuation
controls, sixty original-history cases concern recall/attribution, and twenty
ask about withdrawals. Most continuation declarations are deliberately explicit;
fifteen different-value variants use explicit negatives and five use alternate
values. They do not represent subtle spontaneous preference changes.

The acquisition audit found no repeated persona or complete history against the
prior acquired set, but exact-turn sharing remains: 19 connected components
within the new families and 17 when links through prior families are included.
These are overlap descriptions, not estimates of an independent sample size.
Near-duplicate/template independence has not been established. Passage names in
questions provide retrieval cues, and most factual questions require local
passage extraction. This is not an official held-out benchmark, learned-policy
evaluation, general memory evaluation, or evidence of forgetting.
