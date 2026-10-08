# Why Qwen taskhead reads escape the memory: mechanism and fix candidates (research note)

User 22058: "leave the GPU alone, do further research first". This note uses no new compute. It reads saved Stage A / diagnosis telemetry on CPU and a short literature check. Everything here is descriptive or hypothesis, nothing is proven.

## Our evidence
| # | observation | source |
|---|---|---|
| E1 | At reconstructed init, Qwen reads land on allocated cells (absent ≤ .13) and overlap the bound writes about as much as the toy's do | diagnosis fa0e44d |
| E2 | lr 3e-3: absent 4.7% → 99.6% by update 25. lr 3e-4 (A1): 48.9% at 25, 65.2% at 100 (dose-response with step size) | Stage A a25f79a |
| E3 | Update 0 moves EVERY layer's address MLP by the same norm: 0.200 (A0) or 0.020 (A1), whatever the gradient (0.026–0.56). This is the Adam first step, each parameter moving ≈ lr. The toy's step 0 is 0.093 at the same lr | A0/A1/P2C telemetry |
| E4 | Qwen query vectors share a direction at init (pairwise cos .53–.72); the toy's are diverse (.005–.04) | diagnosis |
| E5 | After the escape, the read spread grows 0.97 → 3.7–3.8 cells (A0) or 1.6–1.8 (A1) while the reads sit off the memory | Stage A dev evals |
| E6 | A1 train loss falls below ln 64 (4.23 → 3.85 by update 90; batch acc 9%) while dev stays at chance. Phase-1 training has filler 0, so the last ~16 bindings are still inside Qwen's 32-token local window: a likely **local-window shortcut**, not memory retrieval (cf. the residual-head shortcut in the 10-07 diagnosis) | Stage A |

## Mechanism (ranked; untested)
- **M1. Coherent Adam steps on same-direction inputs** (best supported: E2, E3, E4).
  - Early Adam updates move each address-MLP weight by about lr, whatever the gradient's size.
  - When every query shares one dominant input direction, that weight change shifts nearly every read address the same way: the reads move as a BLOCK.
  - A few such steps carry the block off the written region. There an all-absent read has zero local read-path gradient, so there is no restoring force.
  - The toy's diverse inputs turn the same-size step into scattered, input-dependent moves. That would explain why the toy kept its reads (E4) and why the drift scales with lr (E2).
- **M2. Leaving is loss-favourable early.** At init the reads carry little usable content (cos(q, bound k) ≈ 0), so they add noise to the taskhead logits (loss 4.23 > ln 64). Zeroing them gives head-bias-only logits, and the loss drops toward ln 64 in the same ~10 updates. M2 may set the *direction* while M1 sets the *speed*.

## Same failure class elsewhere
- **Product-key memory** ([Lample et al. 2019](https://arxiv.org/pdf/1907.05242)): adding BatchNorm to the query network raised memory usage from ~26% to ~80% at 1M slots, with better perplexity. Same class: a learned query map that leaves most of the memory unused, fixed by normalizing the queries.
- **VQ codebook collapse:** a code that is never selected is never updated. The fixes are data-dependent initialization plus resetting dead codes to current encoder outputs ([Online Clustered Codebook / CVQ-VAE](https://arxiv.org/abs/2307.15139v1); [Łańcucki et al. 2020, Robust training of VQ bottleneck models](https://arxiv.org/abs/2005.08520v1)). An all-absent read is our version of a dead code.
- **Anisotropy / massive activations:** pretrained LMs carry a few hidden dimensions orders of magnitude larger than the rest ([Sun et al. 2024](https://arxiv.org/pdf/2402.17762v1); [Roh et al. 2026](https://arxiv.org/html/2603.00029v1)). That is consistent with E4, and a random toy backbone lacks it.
- **MoE routing collapse** and load-balancing aux losses are the standard analogue for routers; this one is from memory, not searched.

## Fix candidates (unsupervised unless marked; ranked by evidence × cost)
| fix | targets | closest precedent | one cheap test |
|---|---|---|---|
| F1 normalize/center the address inputs (BatchNorm or a fixed per-layer mean removal on q/k before the AddressMLP) | M1 | PKM query BN | 100-update A0 recipe + F1: is it kept through 100? |
| F2 an address-only optimizer fix: lr warm-up over about 100 updates and/or address-MLP lr ×0.1 (A1 changed the GLOBAL lr) | M1 | standard Adam warm-up | same, with F2 |
| F3 a restoring force: (a) an unsupervised aux loss on absent read mass; (b) re-anchor all-absent reads to the nearest occupied cell (dead-code reset) | M1+M2 trap | VQ dead-code reset; MoE balance loss | same, with F3a |
| F4 data-dependent init of the address map (spread the actual Qwen q/k over cells: PCA / k-means) | M1 | VQ k-means init | same, with F4 |
| F5 a design change: content-based top-k over occupied cells (never empty) instead of a spatial stencil | trap | PKM, Memorizing Transformers | a separate design track |
| A2 (supervised ceiling, still untested) | — | — | the Stage A A2 arm |

**Recommendation.** When the GPU or Modal is allowed and approved: one 100-update screen with F1 + F2 (both unsupervised and deployable), with A2 as the supervised ceiling. A kept band separates "fixable within this design" from "redesign (F5)". Note that E6 means train loss is not evidence of memory learning in phase 1. Keep the absent-read band as the endpoint.

## Unresolved
- The block-shift size per early step was not measured (it needs a Qwen forward; CPU is possible but RAM is tight while smollm runs).
- Whether M2 is needed at all, or M1 alone suffices.
- The cause of A2's missing GPU and of the 12.7-min scheduling gap.
