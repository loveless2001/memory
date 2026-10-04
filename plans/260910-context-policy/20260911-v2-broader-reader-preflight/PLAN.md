# Reviewed broader reader: raw-source baseline

This continuation prepares and verifies the reader run on CPU. The GPU launch
is a separate bounded action. Preserve both candidate freezes and the independent
parent/delta reviews. Reference coverage is 12 delta accepts plus 108 inherited
accepts, not a new 120-case review. No training or action-label export is included.

## Fixed comparison before reader outputs

Use all 120 reviewed v2 questions, each at zero, one and two supplied retrievals:
360 potential answer captures. Use raw source withdrawals, not manually annotated
UNKNOWN records. The earlier normalized arm combined semantic annotation with
rendering and mislabeled derived content as user text. This broader baseline
does not reuse that intervention. Any future derived arm needs its own explicit
origin and annotation protocol, held separate from raw source evidence.

Keep the existing budgets: notes 768 tokens including the complete recognized
withdrawal ledger, recent context 512, source chunks 384 with 64-token overlap,
each of two retrieval rounds 1,024, output 192, answer 90 whitespace words,
active context 8,192 including output reserve. Use the pinned Qwen3-4B-Instruct-2507
revision and library versions from the preceding experiment. Reader: FP32 math
SDPA, TF32 off, frozen base, greedy decoding, seed zero. Query-blind note selector:
BF16 with constrained source-ID choices and whole-quote budget admission.

Generate twenty original-history notes once. For each synthetic continuation,
branch from the corresponding completed original note and process only its new
user turn. Do not feed one sibling note into the other. Save all actual selector
messages and selections. Query/reference fields do not enter note selection.
The initial CPU audit found 26 user requests starting with `Forget` that the old
`Please forget`-only detector missed. The new version recognizes both explicit
forms and preserves their full text in the ledger; they are excluded from fact
quotation candidates. The initial failed audit is preserved. This grammar still
is not a general paraphrase or deletion-intent classifier; audit other forms.

The revised archive wrapper labels every quote with actual role and Unicode
character coordinates. Partial recent/chunk slices remain exact substrings;
no token decode may alter source text or impersonate a user message. The system
instruction distinguishes source-scoped historical recall from current biography,
including explicitly personal assertions embedded in questions. This changes
the harness identity; do not pool results with the earlier prompt/chunker.

BM25 ranks only the question and source chunks. Freeze selected evidence before
any reference-coverage audit. Reference spans/answers cannot influence notes,
retrieval, runtime prompts, ordering or model generation. Mount only reader
inputs and required implementation files. Counterbalance round execution order
by a fixed hash of question ID, while retaining one complete fresh prefill for
each answer. This is a counterfactual answer-quality probe, not adaptive policy
execution or an end-to-end cache speedup experiment.

## Preflight and prospective execution limits

CPU preparation verifies accepted-reference provenance, source-exact slices,
complete history branches, note workloads, grammar/input bounds and all 360 chat
prefixes using deterministic source-quote selection fixtures. These fixtures are
not generated notes and are not mounted into the reader. Actual note selections
and token budgets must be checked again during the run.

Before any notes or answers, require all forty new-transcript GPU cache fixtures
to pass exact append argmax and sixteen-token-or-EOS trajectory equality under
FP32 math SDPA. This gate cannot be satisfied by CPU checks or a previous harness.
Stop on the first failed fixture or later source/budget/note validation failure.

Proposed launch: one H100 function, forty-minute hard timeout, internal stop at
2,350 seconds, zero retries, one container. Preserve partial artifacts and failure
details; never silently substitute notes, drop cases or restart. The ceiling is
a limit, not a promise of completion. Previous runs took 591.7 seconds for 150
captures with reused notes and 444.3 seconds for 30 captures plus 63 note updates;
these historical timings only motivate the proposal, not a reliable prediction.
No current dollar-price or cost forecast is claimed by this CPU preparation.

## Review after capture

Independent answer review must inspect the actual messages and captures as well
as the reviewed references. Require the conjunction of correct/complete answer,
visible-source support, source consistency, withdrawal/ownership compliance,
EOS/nonempty body/no reserved action marker, and at most 90 words. Report each
criterion separately. Missing evidence can explain a safe abstention but does
not make a historical fact question complete. A lucky unsupported answer fails
visible support. Separate wrong-current-value, restatement-only, ownership,
over-abstention, incompleteness and format/length failures.

Report per question class and retrieval depth, same-family changes, and synthetic
versus original-history cases. There are no learned action decisions here:
`ANSWER` is supplied and action-format compliance remains null. Export no useful
action or training labels. Reference acceptance and source availability do not
establish reader performance. Do not infer forgetting, independent n, or a
generalization gain from this selected synthetic-release probe.
