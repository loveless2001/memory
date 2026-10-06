# P2.5 prereg v0.2 — cleared for implementation and bounded local preparation

Reviewed `3bf87370a7140168c87397e4d0f29b27b5810f22`,
[prereg](../261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg.md), SHA256
`0ce61a096b0c7150e00f0a604ed85cb8f9694584cb70790d43d5fb3d010c2002`.
It resolves R1–R5 from the [v0.1 audit](codex-261006-p2p5-prereg-v01-audit.md).
This is document clearance. No implementation, model execution, fit,
learning, runtime or priced ledger is verified by this review.

## Scope now cleared

Proceed with the versioned pretrained builder, residual readout, genuine
local-only trainer, device plumbing, observer, rules integration and guarded
runner code; run the required CPU correctness/parity checks; prepare the
separate pinned CUDA environment while preserving the CPU environment.
After the required checks, perform only the specified local timing/fit
profile: four configurations, 40 total optimizer updates, four timed dev
batches, 1800-second total wall bound, stop on the first OOM/error, and no
artifact/reserved seed or accuracy inspection.

No Modal deployment/build/profile, paid training, registered local training,
reserved-population readings, automatic retry, tuning, expansion or P3 run
is cleared here. The concrete implementation and admitted charged ledger
still need their audits, followed by the stated scoped user cap approval.
A local fit failure is reported for review; it does not authorize a paid
profile or an alternative precision/batch/gradient policy.

## Resolution and independent checks

| finding | v0.2 resolution |
|---|---|
| R1: raw-read head and zero-feature local-only | All arms use the same initialized and trained 64-class linear head on the final normalized query residual. The output/mix path at layer 27, MLP and final norm are in the answer path. Local-only re-ingests with SGM disabled and trains its head; query snapshots are independent. |
| R2: selected maximum-control interval | Compute every learned-minus-control paired contrast. Each of three controls must receive the both-seed gain label. The maximum mean is descriptive, and normal intervals are a stated deviation from the spec's bootstrap. |
| R3: per-load interface and table | Measure the N32-trained oracle at N32 and at N16 as an explicitly labeled transfer diagnostic. Check each load's own both-seed >=0.50 gate before evaluating its other corners. Invalid inputs/parity prevent headlines. Read-offset failure means use is not established. |
| R4: gradient and profile bounds | Full-gradient token-serial, fresh state, fixed FP32/TF32-off and no automatic approximation. Isolated pinned CUDA environment; four fixed phase/arm timing configurations with explicit updates/wall/OOM bounds. |
| R5: tiny observer assumptions | New bound pretrained/residual-head, arm-aware observer and the 16-head geometry, with disabled-SGM equivalence, frozen optimizer, output-path gradients, causality, device/snapshot/replay and legacy-preservation checks. |

The trained universe is exactly 18 cells: four primary arms x two loads x
two seeds (16), plus two N32 oracle diagnostics. With both interface gates
passing, the reserved report has 20 evaluation corners: four oracle
corners (including N16 transfer), twelve other memory-arm corners and four
local-only corners. The maximum is **53,248 rows**, not 20 x 3,072, because
the four local-only corners contain only the none intervention.

Conditional coverage is registered and intentional:

| eligible loads | oracle corners | other corners | total reserved rows |
|---|---|---|---|
| neither | 4 | 0 | 12,288 |
| N16 only | 4 | 8 | 32,768 |
| N32 only | 4 | 8 | 32,768 |
| both | 4 | 16 | 53,248 |

These counts assume all oracle files are complete; malformed/missing inputs
follow the global unavailable gate. An intentional skipped corner is null,
not a missing trained cell or unexpected partial report. Both oracle loads
are measured even if the N32 interface threshold fails; the N16 transfer
gate is its own measurement rather than an inferred N32 outcome.

Independent enumeration of 512 combinations of input validity, interface,
memory-use and the three four-valued control labels makes the ordered
reading table total. SCREEN PASS occurs only with valid inputs, interface,
memory use and gain labels for every control. The v0.1 selected-control
counterexample is rejected by this conjunction. See
[checks output](codex-261006-p2p5-prereg-v02-checks.json).

## Interpretation and implementation requirements retained

The oracle has inspected each shared reserved population. If a gate fails,
only the other models' corner evaluations remain unconsumed; the whole
population is not untouched. Interpret the draft's parenthetical
"population untouched" in that narrow sense, and record the consumption
state rather than describing those shared episodes as unseen later.

The fixed synthetic task and split remain those of v0.1/P2:
`synthetic_kv_binding_v1`, four queries, 64 value classes, the existing
disjoint train/heldout key/filler ranges and no tokenizer/template switch.
Bind that realized task in the grid and split manifest. The common head
must actually train in memory_off: the old trainer's skip branch cannot be
reused for the new path. Keep raw-read/tiny defaults unchanged for legacy
parity. Require gradients for applicable trainable output/mix groups,
including layer 27; fixed-address groups may be structurally frozen.

The profile is only {learned, memory_off} x N32 x {filler 0, filler 40},
batch 16, stream seed 99, with 2 warmup and 8 measured complete updates
per configuration, and one timed full-filler dev batch each. Record the
resolved configuration, seed, order and runtime environment. Start the
wall bound before model load/forward work; suppress accuracy-bearing
default train/evaluate logs and outputs. The profile never becomes a
checkpoint or a learned-performance result.

Ten updates from fresh initialization do not measure routing/allocation
after 1000 or 1500 updates, and neither oracle, random_fixed, single_cell
nor N16 throughput is measured by these four configurations. A laptop
measurement is also a proxy for the future frozen Modal GPU SKU. Declare
these limits and conservative per-arm/phase assumptions in the ledger;
do not claim all 18 configurations have passed fit/time certification.
The ledger must include actual finite deadlines, evaluation/readings,
build/startup/shutdown, GPU/CPU/RAM, margins and exact first-attempt scope.
Its admissibility and scientific execution remain separate questions.

Two seeds and the N16/N32 scope are accepted only for this exploratory
synthetic classifier interface screen. No LM-answer/KL, mechanism,
matched-storage, scaling or P3 conclusion follows. FP32, feature shift 1,
head/layer geometry and the schedule are registered settings. Existing
CPU/cache facts are recorded in the prior checks; no new model execution
or hardware-fit claim was made in this document review.
