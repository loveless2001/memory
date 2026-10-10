# Independent review: preceding-key information probe proposal v0.1

**Revision required before numerical clearance.** The feature tap, common embedding target, disjoint evaluation keys and episode-level evaluation are suitable foundations. The draft does not yet define a usable negative reading, the primary improvement comparison, complete fitting semantics or a whole-job resource bound. No implementation, model load, forward, probe fit or optimizer step was performed in this review.

Reviewed owner commit `f634d1a`, proposal SHA256 `9f4d707299907beb04a4c672536950d008e90c6fee3a03e41d3d9b05cc1d2b95`. A byte-exact copy is retained here. The previous-key hypothesis and the old campaign's negative result remain separate.

## 1. Negative reading and calibration

An interval that includes chance may also include useful recovery. For example, an interval from .02 to .45 includes 1/32 but cannot support a narrow weak-recovery conclusion. Replace “not linearly carried” with a qualified reading such as **weak linear recovery under this fitted probe**, requiring a predeclared upper bound below a meaningful margin, e.g. .10 at every calibrated layer. This threshold is a proposed diagnostic convention, not a scientific constant. Wide intervals stay inconclusive. Weak recovery still does not prove that nonlinear information is absent.

Specify whether the K control criterion applies per layer and its confidence bound, rather than only a point estimate. A poor K readout can reflect a poor linear decoder, domain transfer or the chosen target representation; it is not independently proof that capture code is broken. Report a layer as uncalibrated when its positive control is inadequate. Declare label precedence explicitly, especially where a strong V result and a failed K threshold coexist.

The “invalid if any null/baseline interval excludes chance” rule combines multiple marginal 95% intervals. It can invalidate a correct experiment because of sampling variation. Predeclare a family-level calibration check or simultaneous intervals, while retaining the raw per-layer diagnostics. Calling the labels operational does not eliminate this multiple-interval issue. NIST distinguishes marginal and simultaneous coverage and describes a Bonferroni construction for a declared family. [NIST simultaneous intervals](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm).

Define the shuffled-pair null precisely: the fit/CV/evaluation partitions to permute, the permutation unit, whether fixed points are allowed and the RNG. Evaluation must remain a separate, declared test of the original true-key task. Include a direct identity-target retrieval check so candidate ordering, zero predictions and tie handling have a verified reference independent of K's fitted decoder.

## 2. Register the append-key improvement

Q2 asks whether V+K improves on V, but the draft has no primary difference or fixed reading for that question. Retain each episode's accuracy for both fits, report **paired V+K minus V** intervals using the same episode bootstrap draws, and predeclare a practical improvement margin if a follow-up will depend on it. Report V+K versus K as a secondary comparison to distinguish an append-key advantage from value features adding information beyond the key control.

Use the same declared episode folds and final episodes across feature sets/layers. Report individual scores and paired differences even if no operational label passes. A better V+K score is evidence for the probe's representation bundle, not a result for the full shift2 runtime.

## 3. Specify the ridge/CV pipeline

“X standardized with fit-split statistics” is not enough for CV: each fold must learn centering/scaling only from that fold's training rows. The final fit then learns preprocessing on all 96 fit episodes; evaluation uses those fixed transforms. This prevents validation-fold information from entering preprocessing. [Official scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).

Fix the ridge objective and lambda scaling, intercept/target-centering treatment, numeric precision, CV selection metric, deterministic tie-break, folds and bootstrap/permutation seeds. Define retrieval ties, rank numbering, zero predicted vectors and nonfinite output handling. Save the selected lambda and fold scores for each declared fit. Key-embedding normalization is the pinned target transform, not an evaluation-fitted transform.

The inner episode CV will reuse many key IDs across folds. That does not invalidate a genuinely disjoint final key evaluation, but it calibrates unseen episodes rather than unseen keys. Record this distinction; if a weak final result is used as evidence for missing information, consider a key-aware inner split instead of treating poor transfer under one selected decoder as an information ceiling.

## 4. Bound the complete numerical job

The proposal specifies memory/swap caps but no overall wall deadline, fit-work limit or failure boundary. A straightforward implementation entails 17,280 token-serial source steps for 160 full episodes. Four layers × five feature sets × four folds × six lambdas give **480 candidate ridge evaluations**, plus final fits. This derived count is not a measured duration; shared factorizations can reduce work, but the algorithm must be fixed and included in profiling.

Set a whole-job deadline covering model verification/load, capture, feature writes, CV/final fits, evaluation, bootstrap and cleanup. Retain per-stage progress, source/parameter identities, memory-control verification, exit status and partial artifacts. Bound BLAS/PyTorch thread counts. Release the backbone before fitting or use a separately bounded fit stage. No automatic retry or counts/arm expansion follows an OOM, timeout or incomplete output.

The proposed two-fit-episode smoke cannot exercise four-fold episode CV. Either declare that smoke as capture plus fixed-lambda mechanics only and verify CV separately with small artificial matrices, or use at least four fit episodes for a full-path smoke. Set smoke-specific seeds/counts and a time bound; smoke results must not trigger scientific labels or be silently reused as final evaluation evidence. Its purpose is finite outputs, indexing, memory behavior and measured capture/fit throughput.

The existing 4400M RAM / 1200M swap cgroup limits are appropriate to retain, but a memory limit is not a deadline. The deleted GPU environment remains outside this CPU proposal.

## 5. Freeze the runtime choice and interpretation

For this first probe, keep the declared seed-0, shift1, SGM-enabled initialization: it measures the actual adapter input. Do not add the nonlinear MLP or a memory-disabled condition to this run; either would be another condition. L6 is upstream of the first memory injection; later layers include initialized SGM effects. Alpha near .018 alone does not bound the magnitude of those effects, so describe their presence rather than certifying them as tiny.

Replace the abbreviated manifest path with the exact path and hash: `plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs/probe-taskhead-learned-n32-s0-run_manifest.json`, SHA256 `4e89b95adcff68b73fecb2f071c3fe17498c7e62fd1a97ac04f77691b5fc0bb0`. The draft references a training PilotConfig; explicitly freeze the diagnostic construction overrides so its `steps:1500` and CUDA device never imply training or GPU work. Record the final resolved config, model files, source/versions and initial adapter parameter hashes when implemented.

The current common normalized embedding target is preferable to a train-key-ID classifier. Strong V recovery would establish that this decoder can access preceding-key information under the declared runtime and population. It would not prove the deployed q/k/address maps can extract or use it. Weak recovery only narrows the particular linear-probe result; it does not by itself clear a shift2 rescue campaign.

## Handoff

Revise the proposal with these fixed readings, paired comparisons, fitting semantics and bounds, then implement the concrete probe for audit. Numerical smoke/full execution remains a separate reviewed and authorized action under the proposal's stated workflow. The user requested ideas and review; no new numerical execution was authorized in the messages reviewed here. No paid follow-up, P3, nonlinear probe or environment rebuild follows automatically.
