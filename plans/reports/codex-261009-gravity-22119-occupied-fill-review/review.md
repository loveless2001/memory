# Independent occupied-fill implementation review

Candidate: `m4-sgm-occupied-fill-v1` at a66d800c4d4d4e10b0a4015d6f904d7b1b9a2562, compared with 95856b153e874508726c604a8c593c6ff73684cb. User 22113 authorizes CPU preparation/checks only. **Hold clearance for the numerical correction below.** Keep this variant on the side branch; do not relax frozen campaign source/parameter bindings to accommodate changed code. No GPU, Modal, Qwen forward, merge or mvp source change was performed.

## Finding: missing mass must be computed directly

In `occupied_cell_read_fallback.fill_read`, the fill and anchor coefficients use `1 − sum(w * present)`. Quadratic B-spline weights sum to one mathematically, but FP32 sums need not equal exactly one. A fully occupied stencil can therefore receive a nonzero fill and anchor. When the rounded present mass exceeds one, both coefficients become negative and the tiny anchor gradient points away from its target. This violates the advertised exact supported-read behavior and nonnegative anchor.

The independent reproducer uses ordinary cell values, not extreme magnitudes:

| Fully occupied read coordinate | Computed present mass | Fill | Anchor |
|---|---:|---:|---:|
| (0.76453853, 0.83000791) | 1.0000001192092896 | −5.4542e−7 | −4.9253e−9 |
| (−0.40615833, 0.66337097) | 0.9999999403953552 | +2.1794e−7 | +7.7851e−9 |

In both cases, the read changes bitwise even though every stencil cell is present. The direct sum `sum(w * absent)` is exactly zero. Compute this missing mass directly, as the existing `EmptyReadWeight` does, and use it in both fill and the detached anchor coefficient. Merely clamping `1−m` would still produce a spurious positive fill for the below-one case. Preserve raw present-mass/all-absent semantics or derive those from the presence/weights consistently. Add exact fully-supported checks at fractional coordinates; the existing approximate assertion misses the issue.

Evidence: `independent-kernel-check.py` and `independent-kernel-results-a66d800.json`, bound to module SHA256 a6963f60e488b3d64ff228dc8a164beb856a1cdf76fecd52fd6307838406fda2. The numerical effect is small; it is a contract/precision defect, not evidence that this mechanism causes the original escape.

## Verified CPU behavior

- All 12 new candidate tests pass independently.
- The isolated four-update tiny default-off fingerprints match baseline exactly: parameters `0569712a…`, telemetry `36ee6107…`, policy `m4-sgm:learned:sha256:51d7a1e03f11753d`. These are parity/mechanics checks, not learning results.
- The 31 unique existing core/runtime/resume checks pass. The first invocation had 30 passes and one missing-script error because my isolated archive omitted the frozen-runtime observer helper. I restored that helper from the exact candidate commit and reran only the affected check; it passed. Both logs are retained. This was a review-fixture issue, not a candidate regression.
- Independent finite differences for a partially supported read agree with autograd to approximately 9.94e−5, including the differentiable missing-mass task path.
- For the far-empty anchor at (7,−3), the exact nearest occupied coordinate is (1,0). The measured derivative equals `(a−nearest)/sqrt(1+distance²)` componentwise. This is stronger than merely checking a positive dot product toward a nearby point.
- Source inspection and runtime tests support unchanged ingestion code/banks at matched parameters, raw pre-fill absence telemetry, attached stored-content graphs, and the specified anchor reduction. Banks from separately trained variants will naturally diverge as parameters diverge. Stored-state derivative `π_j q` applies to a fully absent read; partial support also includes stencil and missing-mass factors.

The fill spans all occupied cells, not a fixed nearest-k set. The rule/spec makes this explicit. Its per-query memory/time cost grows with occupancy and remains unprofiled. The anchor targets any occupied cell, not necessarily the bound value. Filled support, original routing retention and useful retrieval remain separate outcomes. The short gate is designed around routing/mechanics; it is not a general claim that useful retrieval could never emerge within 100 updates.

## Frozen evidence and suite failures

The recorded owner suite has 37 failures: 12 also fail on unchanged baseline, plus 25 changed-source guard refusals. I verified that these two recorded ID sets are disjoint and exactly cover the reported failures. I did not rerun the entire suite. The provenance guards must continue rejecting new source when asked to validate the closed campaign.

The cleanup receipt, amendment spec and current filesystem independently confirm deletion of:

`plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1/learned-n32/volume-evidence/collect-1/learned-n32/cells/learned-n32-s1/epoch-1/gen-30-step1500.pt`

Expected bytes: **26,599,561**; SHA256 **38982aab52b02bf3c666431e10e87d3ae64ebb41da0c6de5331e9655f2f94801**. My earlier preservation review missed this amendment dependency. A narrow search of retained local pytest copies found no matching terminal filename. The similarly named taskhead-probe checkpoint belongs to a different run and cannot substitute for it.

The saved revalidation record/readings remain historical evidence, but the exact amended gate cannot now be revalidated locally without the original blob. Do not fabricate an equivalent checkpoint, silently skip these failures as successes, or rewrite bindings. A later exact-hash recovery may be possible from the old remote volume; no Modal access was made under this CPU-only scope.

## Next boundary

After the missing-mass correction, review the new commit and rerun the affected exact-support/gradient checks. Broader repeats are needed only if integration changes. An implementation clearance would allow preparation of a concrete bounded proposal, not a model launch. The side-branch source must receive its own package/dependency identities rather than reuse the frozen Stage A launcher unchanged. No 100→1500 continuation or paid experiment is cleared here.
