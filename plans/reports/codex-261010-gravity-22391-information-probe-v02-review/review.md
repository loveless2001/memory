# Information-probe proposal v0.2 review

**The design is ready for implementation preparation and model-free C0 checks, with two corrections required before numerical execution.** The previous review's negative-reading, paired-improvement, fitting and frozen-condition requirements are substantially addressed. No backbone/model load, forward, probe fit, optimizer or paid work was performed here. The proposal itself authorizes no execution.

Reviewed owner commit `6e8b604`; the exact `proposal-v0.2.md` is copied into this folder and hash-bound in `manifest.json`. Previous proposal and review artifacts remain unchanged.

## Accepted revisions

- Weak recovery now requires a small upper bound at calibrated layers, while wide intervals remain inconclusive. The K criterion and label precedence are explicit; decoder failure is separated from broken capture.
- Q2 has a paired episode-bootstrap V+K−V comparison and a practical improvement reading. V+K−K is separately descriptive.
- Fold-local preprocessing, the unnormalized ridge objective, unpenalized intercept, float64 SVD, lambda grid, selection metric, deterministic ties and final refit are specified.
- Fit/evaluation key families are disjoint. Episode CV's reuse of key identities is disclosed.
- Null/baseline and per-statistic layer interval families have specified adjustment levels. These are approximate bootstrap intervals; the four-layer adjustment for each statistic should not be reported as a single joint 95% guarantee over all K/V/contrast decisions together.
- The runtime is one declared SGM-enabled seed-0 initialization on CPU, under no-grad, without an optimizer. The tap is the actual normalized pre-attention project input; later-layer SGM influence is acknowledged. No nonlinear or memory-disabled condition is added.
- C0, capture smoke, full-path smoke and the final run have separate roles. Smokes do not receive scientific readings, and failures retain partial evidence without automatic retry.

## Required correction 1: the shuffled null's reference

V-shuf uses a derangement in both fit and evaluation, excluding each row's actual preceding key. The proposed INVALID reading still compares it to 1/32. That is not a general valid null reference once the features expose the original key.

Exact counterexample: if a decoder can identify the original key, it can exclude that candidate and choose another. Under a uniform derangement, the shuffled target is uniform among the other 31 keys. A prediction that always selects another key therefore has expected top-1 **1/31**, not 1/32. With two keys, the deranged target is deterministically the other key and can be recovered perfectly. This is not pipeline leakage; it is information supplied by the null's exclusion constraint. These are mathematical counterexamples, not new model measurements.

The clean correction is an **independent uniform permutation with fixed points allowed** for evaluation targets, using the declared independent evaluation RNG. Conditional on the fixed prediction and episode candidates, each target index is then uniform among 32; unique top-1 predictions have expectation 1/32. Use the corresponding full permutations for fit/CV if V-shuf is to remain a fitted null. Reuse one permutation per declared episode rather than changing it across folds/lambdas. Update C0 from “derangement has no fixed points” to testing the permutation mapping, partition separation and independence from predictions.

Alternatively retain derangements but calibrate the null against its actual conditional permutation distribution and revise the invalidation rule; do not label a score above 1/32 as a capture failure solely under the existing deranged construction. Either choice must be fixed before observing probe results.

## Required correction 2: deadlines and fitting estimate

S1 currently determines the full-run wall estimate, but neither S1 nor S2 has an explicit numeric wall timeout. Assign finite limits before their model loads; the timeout must cover load/capture/fit/output/cleanup for each invocation. Fix the full-run estimate formula and the admission rule: if twice the estimate exceeds four hours, stop before the full launch rather than silently clipping an infeasible estimate.

A two-fit-episode S1 gives only **64 fit rows**, whereas full CV train folds have **2,304 rows** and final fits **3,072 rows**, with input dimension 1,024 or 2,048. Economy-SVD work depends on matrix dimensions and rank; multiplying a 64-row fit duration only by the episode count does not account for the rank increase. Specify a dimension-aware conservative estimate or an appropriately authorized fit-profile stage, including candidate-prediction work, bootstrap/output and model loading. Label any extrapolation as an estimate rather than a measured completion guarantee. The four-hour hard ceiling remains valuable even if the estimate is imperfect.

The 80-CV-SVD/20-final-fit count is a reasonable upper work description for the declared four-layer/five-set implementation. Some sets can reuse work, but optimization must preserve the registered fits. Ensure the concrete code releases captured model/state before the large solves, retains detached features and bounds both PyTorch and BLAS threads within the cgroup. S1/S2 failures must stop the progression; passing output JSON plus exit status, rather than a wrapper's completion string, admits the next step.

## Handoff

Proceed with the concrete implementation and model-free C0 work, incorporating these corrections in a new preserved proposal revision. Then supply source identities, checks and launch commands for implementation audit. CPU smoke/full numerical work remains subject to that audit and the user's scoped go. No extra fit counts, conditions, retries or paid follow-up are cleared by this review. The prior Qwen campaign stays closed with its original results.
