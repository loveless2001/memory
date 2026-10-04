# Paired reader repair — prospective plan

The user authorized this paired repair experiment with “go ahead” after the
proposal to keep chronological presentation fixed, test one procedural reader
instruction, compare existing and fresh cases, and require both gates to pass.
This authorizes one bounded inference run and its analysis. No training, broader
pipeline run, automatic paid retry or external judge is included.

## Frozen comparison

Both arms use the existing JSON archival wrapper, full chronological source
turns, original role/turn/character labels, identical questions, the same frozen
Qwen3-4B reader and the supplied ANSWER prefix. Only the system instruction changes:
`baseline` is the previous instruction; `repair` is one procedural rewrite that
resolves question scope, owner, chronological assertions, withdrawal to UNKNOWN,
later reinstatement and permissible final answer. No demonstrations, derived
state annotations or reference answers are provided to the model. This is a
bundled instruction intervention, not an isolated estimate for each rule.

The 24 previous diagnostic cases are an unchanged development regression set.
Fresh cases use four new families: weekend activity (bouldering/kayaking), evening
activity (origami/chess), snack fruit (mango/kiwi) and cold drink (lemonade/iced
coffee). Each family has baseline, withdrawal, later different, later same,
historical and fictional-owner cases. Every source is asked in binary and
open-value forms: 4 × 6 × 2 = 48 fresh cases. This crosses question form with
the same topics and evidence, avoiding the previous topic/form confounding.
Historical binary questions concern what the original text said. Fictional
lines are framed as copy-editing text from character Vale. Family, source and
question variants are related; 48 is not an independent sample size.

Total: 72 cases × 2 arms = 144 captures. References and questions are authored
before generation. The candidate prompt is fixed before reading outputs and is
not revised after generation. Per-case arm order and forty cache fixture indices
(twenty per arm) are fixed by hashes. Existing baseline inputs must be byte-for-byte
equivalent to the previous JSON chronological inputs. Their output token equality
is checked descriptively against the earlier run; no new matched baseline is
replaced by a historical score.

## Review and gates

Review all answers against full sources and actual reader messages, recording
criterion judgments, reasons and exact quotes. This is unblinded author review,
not independent benchmark validation or training-label admission.

Strict pass requires: task completeness/correct current value; consistency with
source; whole-answer visible support; withdrawal compliance; speaker ownership;
EOS/nonempty/no additional action marker; and at most 90 words. Report required
value/task correctness separately from strict pass. UNKNOWN is neither a negative
nor no preference. A direct user assertion persists absent a later change; no
unspecified time gap or reconfirmation requirement may be invented. Historical
answers preserve the question's textual scope and may quote the original value.

Current-scope explanations must not restate a withdrawn old assignment. Naming
only the topic does not fail. A concise direct yes/no response about the questioned
value is judged as a current-state claim; it is not automatically an explanation
of withdrawal. Repeating an old named value while explaining its withdrawal does
fail. A later explicitly re-established same value may be stated. Do not infer
physical erasure from ordinary “forgotten” phrasing, hidden reasoning from an
uncited answer, or an ownership error from a clearly scoped first-person echo.
Missing citations alone do not fail. Resolve ambiguous outputs explicitly and
count ambiguity as nonpass for gates, without silently changing criteria.

The repair succeeds only with **24/24 strict development passes AND 48/48 strict
fresh passes**, including all six classes and both fresh question forms. Report
paired corrections and regressions for both splits and every class. A pass would
justify proposing a separate transfer test in the actual broader pipeline; it
would not establish training readiness. A failure stops this prompt experiment
and motivates investigating explicit source-backed state tracking. Do not launch
another prompt variant or a broader run automatically.

## Execution and provenance

One H100, four CPUs, 32 GiB RAM; 1,200-second hard ceiling and 1,150-second internal
deadline; zero retries. Pinned reader revision, FP32 math attention, TF32 disabled,
seed zero, greedy decoding, fresh prefill, 192-token generation cap, 8,192-token
context cap. Before captures, forty actual-prompt cache fixtures must pass
initial-argmax and sixteen-token-or-EOS cached/fresh trajectory equality.
Stop and preserve partial artifacts on cache or runtime failure.

Mount only allowlisted implementation, config, input messages and gate indices;
references stay local. Hash-bind preflight files, source snapshots, captures and
review. Preserve previous experiment files and reviews unchanged. Verify model,
template, token IDs, EOS, budgets and counted forwards offline; report actual
elapsed time, observed billing and terminal app state. Cache correctness and
artifact integrity do not establish semantic correctness.
