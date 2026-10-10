# P2G preregistration v0.1 audit

Verdict: **amendments required before implementation**. No training or new
model evaluation was run. This audit reads the draft, code, saved manifests
and walls, and computes an admission ledger with existing pure guard code.

Audited document: `86e9bab`,
`plans/261006-0010-m4-sgm-p2g-selective-write-gate/prereg.md`, SHA256
`1c5dd5c3d24bd94f830a46f75665c18d915c7d82274bc02e493dbd80ad8f4da0`.
Base evidence: Step 2 closure `cb452fb`.

The six-cell scope, fixed step-1500 endpoint, fresh episode-paired seed,
full train-write/eval-write table, paired half-oracle contrast, and existing
memory-use rule are suitable for a bounded diagnostic. The proposed fixed
bias -3 and pooled ratio threshold 0.20 are acceptable preregistered design
choices; freeze them without tuning after seeing results. Their scientific
meaning and several input/decision contracts still need the changes below.

## 1. Bind old checkpoints and the evaluation runtime

Lines 21 and 25 do not specify an executable runtime for all comparisons.
Frozen `1d62903` evaluation has no `filler_writes` argument or skipped-write
ingest path. Existing v2 checkpoint manifests have source `a89284ea…` and
git `1d62903`; existing filler-off N16 manifests have source `d4effd0c…`, git
`31aa4c8`, and group `p2d-diagnostics-v1`. The new gate code will have another
source identity. Preserve these identities rather than rewriting them as
new-group artifacts.

Register the checkpoint index and hashes, exact training configuration,
analysis source/code hashes, and a separate evaluation-write override for
each T/E corner. Validate all identities before evaluation. Establish that
the common observer's E=on path agrees with frozen v2 on fixed checkpoint
fixtures before using its E=off extension. The default-build parity test
alone does not validate an evaluation extension.

These training cohorts also inherit the unresolved seed-0 prefix discrepancy
already recorded in Step 2. Retain that limitation. Same episode hashes make
the evaluation comparisons paired; they do not establish identical training
histories across the historical sources/hosts. With these reused checkpoints,
phrase Q2 as registered contrasts between the training recipes and evaluation
settings, without asserting that a unique causal training blocker was isolated.
Similarly, Q1 compares the new gate recipe to historical v2, with that limit.

## 2. Match the selectivity claim to the registered statistic

The primary rho statistic is pooled class-mean suppression. A low pooled
ratio does not itself establish token-level ranking or suppression at every
head/layer. Per-head AUROC is descriptive in this draft. Either narrow the Q1
headline/readings to **registered pooled filler suppression**, or preregister
the additional token/head criterion required for the stronger claim. Failure
of rho also does not justify "not attributable to gating"; use "gain without
registered pooled suppression; mechanism unresolved".

Define the event population exactly: four batches of 16 are 64 episodes,
not 64 episodes times another batch axis. With two layers and two heads,
there are 10,240 filler events at either load, and 8,192 binding events at
N16 / 16,384 at N32, before any explicitly defined exclusion. Skipped filler
events contribute effective zero to the pooled class means. Require finite
beta values and a positive binding mean; zero/invalid denominators fail
closed rather than passing via an epsilon or coercion.

For AUROC, distinguish an absent/skipped write from an applied write whose
beta is numerically zero. Fix whether masked events enter its populations,
and how head mean/min are reported when a head is undefined. Preserve all
four head values and the projected/effective distinction.

## 3. Make the decision tables total

Lines 17 and 33 must have one consistent ordered classifier: reproducible
gain, else excluded positive gain >=5pp, else neither. The blanket fallback
"no registered gain" must not label a contrast that passes reproducibility.
The exclusion is a bound on a positive >=5pp gain, not proof of no effect.
Apply the measured intervals at N32; do not preassign its eval contrasts to
"neither" or "excluded" because point accuracies are near chance.

Specify Q2's four combinations of the training-contrast conjunction and
evaluation-contrast conjunction, including both passing. The descriptive
interaction does not change those predeclared labels.

For Q1, make `half` explicitly null/undefined when the oracle gain fails
its prerequisite, and give this an explicit reading. Do not convert null
to false and silently label it a failed half-oracle comparison. Define a
priority table for gain, suppression, memory use and the three half statuses,
while retaining every underlying flag and interval in the report.

## 4. Correct the initialization description

`beta = sigmoid(W_beta x + b)`, and the existing beta weights are random,
nonzero weights. Sigma(-3)=0.047 and sigma(0)=0.5 are intercept/zero-input
probabilities. They are not every token's initial gate probabilities.
Register this as a bias shift toward smaller writes; keep W_beta and all
other draws unchanged. Include the field in run/parameter provenance and
diagnostic identity even though SGMConfig/policy_id remain unchanged.

## 5. Correct the budget ceiling and freeze the launch contract

Using the exact seed-specific v2 full-cell walls, wall factor 1.0 for both
new arms, the existing 1.4 timeout multiplier, and the existing top-up
overheads/margins gives these timeouts:

| cell | seconds |
|---|---:|
| gateclosed N16 s0 | 6106 |
| gateclosed N16 s1 | 4640 |
| gateclosed N32 s0 | 8773 |
| gateclosed N32 s1 | 6952 |
| filleroff N32 s0 | 8773 |
| filleroff N32 s1 | 6952 |

At four physical cores / 8 GiB and 3x CPU/memory prices, the rate is
$0.757728 per container-hour. Current published rates and the multiplier
agree with the existing guard. See [Modal pricing](https://modal.com/pricing)
and [non-preemptible Functions](https://modal.com/docs/guide/preemption).

| reservation component | USD |
|---|---:|
| training timeouts | 8.88141408 |
| startup and teardown | 0.45463680 |
| replay allowance | 0.53040960 |
| CPU-overuse margin | 0.66332112 |
| image build | 0.30000000 |
| fixed margin | 1.50000000 |
| **total** | **12.32978160** |

This calculation **fails** the proposed <=$12 ceiling. Expected spend is
different from admission reservation. Amend the proposed cap or explicitly
register/review a different deadline policy; obtain the user's actual cap
only after the exact ledger and implementation are reviewable. Do not change
shared guard budgets or reuse the old top-up group/claims/IDs. Register a
new group's exact six cells, configs, source/runner identities, attempt rules,
all billed startup/idle/build/replay bounds, persisted call tracking and
stop verification. Reusing the previous launcher requires a new scoped
runner because its authorized IDs and group are hardcoded.

The local alternative still requires authorization for the training run.
It has no Modal compute charge; its proposed two-hour duration is an estimate,
not a measured local six-cell throughput result.

## 6. Resolve the authorization-order wording

Line 4 appears to require the paid cap approval before code, while line 56
puts implementation before that approval and the channel handoff requests
prereg clearance before implementation. State the gates consistently:
prereg clearance for implementation/preflights; implementation audit plus
scoped user training authorization and the reviewed cap before execution.
Define the allowed CPU unit preflights separately from the six training cells.

Please amend and commit the preregistration for re-audit. The Step 2 report,
rules and evidence remain closed and unchanged by this audit.
