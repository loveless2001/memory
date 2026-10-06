# P2.5 prereg v0.1 audit — HOLD

Reviewed draft `59ca18d`,
[prereg](../261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg.md), SHA256
`53aae9c31e48bc51bd65b6c288dec81bc8fc1aef95dea607dae24b39d38e3ae0`.
This is a registration audit, not an implementation or launch clearance.
The user authorized drafting and building P2.5 in #gravity 21420, following
the stated audit/profile/priced-cap gates. No paid cap or registered local
training is approved. This audit performs no model forward, training or
paid launch.

The pretrained synthetic screen is a reasonable next scope, but v0.1
does not yet implement its claimed local-only comparator or frozen-model
interface question. Five revisions are required before prereg clearance.

## R1 — use a common, meaningful model-output readout

Draft lines 25 and 35–38 retain a head over raw memory reads and supply
zeros to the memory-off arm. Current `query_logits` does precisely that;
`build` gives the head only `layers * heads * value_dim` inputs. This is a
zero-feature ablation, not the spec §15 local-window-plus-sinks baseline.
Source ingestion can leave old information in contextualized surviving KV
even after the bindings' own KV positions are evicted. Its usefulness must
be measured rather than excluded by the readout.

The head also bypasses the final selected layer's injected output and mix
path. `SGMModelRuntime.step` exposes raw reads and optional LM logits;
the raw-read head never consumes the final residual after its injection,
MLP and final normalization. A positive oracle/raw-read score therefore
does not establish that the pretrained model's final output uses injected
memory reads. This matters because the agreed P2.5 follow-up specifically
asks whether a pretrained residual stream can use those reads.

Preferred revision: give every arm the same trained 64-class head on the
final normalized query residual, with identical head initialization,
objective, updates and data. Train a genuine memory-off/local-only head;
re-ingest the source with SGM disabled for that control, not merely at
query time. Preserve independent query snapshots. Update the cell count
and eventual ledger accordingly. This remains a synthetic classifier
interface screen, not pretrained LM-answer, teacher-KL or P3 evidence.

Alternatively, retain the raw-read head but explicitly call the study a
pretrained-feature routing probe, drop the real local-only/spec-screen
claim, and do not use it as the asserted pretrained output-interface gate.
Do not silently switch readouts during implementation or after results.

## R2 — define inference against all controls

Draft lines 43–44 select the highest observed control accuracy and assert
that its paired interval can only make the rule harder. That assertion is
false: interval width depends on the paired episode covariance, not just
the means. The saved stdlib counterexample uses 256 four-query episodes:

| arm | accuracy | learned minus control | 95% paired interval | gain test |
|---|---|---|---|---|
| learned | 50.0000% | — | — | — |
| higher-mean control | 44.9219% | +5.0781 pp | [3.8436, 6.3127] pp | pass |
| lower-mean control | 44.5312% | +5.4688 pp | [−0.6314, 11.5689] pp | fail |

The same construction for both seeds satisfies the draft's gain rule for
the selected comparator while failing its uncertainty requirement against
another control. This is a constructed arithmetic example, not model data.

Simplest revision: retain all learned-minus-control paired contrasts and
require every control to pass the registered both-seed gain rule. This is
a conjunction, not selection of a favorable interval. Keep the largest
observed control mean as a descriptive summary. Alternatively register a
valid paired bootstrap of learned mean minus the maximum control mean,
reselecting the maximum inside each resample, with its seed/resample count,
interval method and total reading table fixed in advance. The spec proposes
episode bootstrap; retaining the P2 normal intervals should be an explicit
screening deviation rather than an assertion that all spec analysis is reused.

## R3 — make the per-load gate and complete reading table explicit

Draft lines 40–48 offer per-N conclusions but only an N32 oracle gate.
An N32 score does not measure the N16 diagnostic. Register a same-load
interface check at both N and both seeds. This can use the two N32-trained
oracle checkpoints at N16 as an explicitly labeled transfer diagnostic,
or add independently trained N16 oracle cells. Bind the actual consumed
checkpoint and population in either case; no inferred N16 pass.

Fix the final population, batch/episode/query counts, intervention set,
episode hash matching, schema/completeness checks, dev populations and
seed separation explicitly. Reusing rules must not depend on accidental
observer defaults. Define how an interface failure, missing seed/cell,
malformed/nonfinite artifact, or failed parity prevents a headline. Specify
whether oracle checks precede other reserved evaluations and how untouched
populations are retained when a gate fails. Preserve null/unavailable values.

A read-offset lower bound <=0 means the registered read-address-use test
is not established. It is not, by itself, proof of dead routing. Use that
narrow label, or separately preregister measurable dead-routing telemetry.
Specify stop conditions as validation/reading gates after the fixed run;
they must not become adaptive early stopping or a tuning signal.

## R4 — freeze the gradient, environment and bounded profile contract

The live project environment is `torch 2.7.1+cpu`, CUDA build null,
`cuda_available=False`, Transformers 4.55.2. The laptop is an RTX 3060 with
6144 MiB. The pinned cache contains 596,049,920 stored BF16 parameters;
converting the weights alone to FP32 requires 2,384,199,680 bytes, before
KV, numerical banks, autograd activations and other overhead. This is
derived arithmetic, not a full-gradient fit measurement.

Use a separate pinned CUDA environment/image; leave the existing CPU
environment and dependency pins intact. Register full-gradient token-serial
ingestion, fresh episode state after each update, no student `no_grad`,
no detached-source substitute, and no side-effectful activation checkpointing.
An OOM does not authorize bf16, reduced global batch, quantization, offload,
chunking, detached ingestion, or another profile configuration. Any intended
alternative needs its own recorded protocol before its performance is read.

Bound the profile with an enumerated arm/N/phase/config matrix, fixed
development seeds, warmup and measured updates within the existing <=50
limit, a total update/config and wall-time bound, and a failure/termination
rule. Demonstrate a complete forward/backward/optimizer step at the actual
batch/sequence/gradient configuration before projecting cost. Suppress
accuracy and selection; never use artifact or reserved seeds in the profile.

Freeze the Modal GPU SKU, environment/precision and finite deadlines before
the priced ledger/cap request. A 6GB laptop measurement is not a measured
24GB Modal runtime; state any throughput-transfer assumption. Include
both curriculum phases, dev/final evaluations, registered readings/parity,
GPU plus CPU/RAM, builds/startup/shutdown and fixed margins in the admitted
scope. Keep first-attempt claims, no automatic training retry, persisted
call IDs, watchdogs and stopped/zero-container verification. A fit/profile
failure returns for review; it is not permission for paid profiling.

## R5 — bind the new observer rather than importing tiny defaults

The existing common observer loads `build()` for a tiny random backbone,
checks exactly layers {1,3} x heads {0,1}, and gathers gate events by
ingesting with literal arm `learned`. It is not a pretrained/16-head/oracle
observer as currently written. P2.5 needs a bound builder/readout/device
and a registered 16-head set (layers {6,13,20,27}, heads 0–3). Oracle
addresses belong only to the diagnostic; disabled/undefined telemetry is
explicitly unavailable, not a fake complete zero population.

Bind actual model revision/file hashes, resolved SGM/readout/compute
configuration, analysis/runner/source/prereg/grid/index bytes, execution
environment and checkpoint identity at start and end. Fix CPU data sampling
and canonical row hashing before device movement. Verify legacy complete
P2G/P2C parity and default-trainer fingerprints; add pretrained disabled-SGM
equivalence, frozen-backbone exclusion from the optimizer, output-path
gradients, causal leakage rejection, device/snapshot correctness and replay
checks for the new path. Keep closed evidence and unchanged decision rules.
Define GPU tolerances/TF32 policy; CPU bitwise preservation is not a claim
that CPU and CUDA arithmetic are bitwise identical.

## Accepted scope choices and next step

Two seeds are acceptable for an explicitly exploratory N16/N32 screen;
they do not satisfy the full reference pilot's proposed three-seed minimum.
Omitting N8 is a scope choice, not evidence that pretrained N8 already works.
Feature shift 1, valid layers (6,13,20,27), FP32, and the fixed P2C schedule
are defensible preregistered settings. P2C's success does not validate a
different pretrained backbone/readout/geometry. A nonfit must stop rather
than silently change those settings. Report the 2048-cell-per-bank limit
as a realized deviation from the spec's 1024 default, plus actual resident
bytes/access and trained parameters; make no matched-storage/scaling claim.

The pinned model's local config agrees with the
[official revision config](https://huggingface.co/Qwen/Qwen3-0.6B-Base/raw/da87bfb608c14b7cf20ba1ce41287e8de496c0cd/config.json).
Model identity/cache presence are verified; fit, runtime, learning, price
and implementation correctness are not. Reproducible read-only evidence:
[checks source](codex-261006-p2p5-prereg-v01-checks.py) and
[checks output](codex-261006-p2p5-prereg-v01-checks.json).

Next: revise and commit the prereg, then audit the revised document. Only
after clearance proceed with the scoped implementation and bounded CPU/GPU
preparation. Submit the concrete audited grid/ledger for the later user
cap approval. There is no P3 or paid/local registered-run clearance here.
