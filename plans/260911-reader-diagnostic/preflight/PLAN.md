# Frozen reader presentation diagnostic

The user authorized completing preparation, execution and result analysis without
another approval checkpoint. This is the diagnostic proposed after the broader
review, not a retry of its 98 uncaptured conditions or permission to train.

## Design before outputs

Four fresh synthetic topic families each supply six cases: current positive
baseline, withdrawal to unknown, later different value, later same value,
historical recall of the original statement, and fictional-speaker ownership.
Two families use yes/no activity questions and two use named-value preferences.
References are authored directly from these short sources before generation.
They are diagnostic author references, not independently reviewed benchmark data.

Every case is crossed with a 2x2 presentation factorial:

- Plain source wrapper or the existing JSON archival-notes wrapper.
- Original chronological order or moving all explicit withdrawal user turns
  to the end of the displayed archive while preserving original turn numbers.

All four conditions include the exact same complete source turns, role labels,
character coordinates and question. No derived UNKNOWN label, reference answer,
query-specific source selection or model-generated notes are supplied. The two
no-withdrawal controls have identical chronological/withdrawals-last inputs and
therefore serve as deterministic duplicate-input checks. The base system
instruction, model, precision and decoding remain fixed across conditions.

This isolates short-form wrapper and source-order effects. It does not reproduce
long-history distraction, lossy note selection, the full legacy withdrawal
ledger, retrieval quality, or learned action policy behavior. Those require
separate experiments. The sources and formatting are deliberately simple and
synthetic; four related families are not an independent benchmark sample.

## Execution and verification

Collect all 24 cases × four conditions = 96 captures. Condition order is fixed by
a hash per case before inference. One H100, four CPUs, 32 GiB RAM, twenty-minute
hard ceiling, internal stop at 1,150 seconds, zero automatic retries. The pinned
Qwen3-4B-Instruct-2507 reader uses FP32 math attention, TF32 off, seed zero, greedy
decoding, supplied ANSWER prefix, fresh prefill, maximum 192 output tokens and
90 words. No selector inference or training is involved.

Before collection require forty actual-prompt cache fixtures (ten per arm),
checking initial argmax and sixteen-token-or-EOS cached versus fresh trajectories.
Stop on cache, source, budget or deadline failure and preserve partial artifacts.
The image allowlist mounts only implementation sources, configuration, messages
and gate indices. Full references remain local. Hash-bind prior experiments and
reviews, new inputs, source snapshots, outputs and author judgments.

## Prospective interpretation

Report raw output and every condition, including format failures. Judge required
answer correctness/completeness, source consistency, whole-answer visible support,
withdrawal/ownership, EOS/nonempty/no extra action marker and ≤90 words. Unknown
is distinct from a negative or no preference; later assertions may establish the
same or different value. Historical and fictional statements retain their scope.
Missing a citation is not a failure. Do not infer hidden reasoning from a correct
answer alone; judge any explanatory claims actually asserted.

Author model review is sufficient for this diagnostic's descriptive report; it
is not an independent review or a training-label admission. Preserve per-answer
reasons and source evidence. No paid external judge or additional agents.

The primary candidate, JSON chronological, passes the strict diagnostic gate
only at 24/24 under all criteria, including 4/4 in each class. Evidence that order
helps requires at least one correction of a JSON withdrawals-last failure with
no newly introduced failure among the same 24 cases. Otherwise report a mixed
or null effect. Compare the plain pair and serialization contrasts separately.
No selection of a winning prompt after inspecting outputs; no automatic follow-up
GPU run. Even a perfect small diagnostic does not authorize training or establish
transfer to the frozen broader suite.
