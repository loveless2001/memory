# Why Qwen taskhead reads escape the memory: mechanism and fix candidates (research note, r3)

## Reconciled findings

r3 integrates codex's independent review 22067/22068 throughout the note and corrects remaining contradictions in r2 (ab775d2). Earlier wording remains in git history; experimental artifacts are unchanged. Detailed equations, CPU examples and input hashes: `plans/reports/codex-261009-gravity-22059-address-gradient-review/`.

1. **No universal repulsion.** For a zero-initialized bank after one write, r = β(q·k)·v·K(a_read, a_write). This special case is not the general formula for an arbitrary occupied bank or a multi-write recurrence. The routing gradient's sign depends on (∂L/∂r)·v and q·k. In codex's fixed CPU example, a helpful stored value gives ∂L/∂read-x = +0.266 (descent toward the write); a harmful one gives −0.417 (descent away). So M2 ("leaving is loss-favourable") is conditional. It can equally be served by shrinking head/v/β/content alignment, and it does not uniquely select a spatial escape or the observed negative q·k.
2. **M1 needs differential motion.** The AddressMLP is SHARED by reads (input q = normalize(W_q z)) and writes (input k = normalize(W_k z)). At fixed features, a shared shift of the AddressMLP output, such as its final bias, translates reads AND writes equally, so a coherent Adam step plus high q-similarity does not by itself explain why they SEPARATE.
   - Separation needs read and write addresses to move DIFFERENTLY: different W_q vs W_k updates, or different AddressMLP Jacobians at the (tight) q-cluster vs the (tight) k-cluster.
   - That differential motion is the missing measurement. M1 is restated as: "anisotropy makes reads one tight block and writes another; early Adam steps move each block coherently but at different velocities". This is still a hypothesis.
3. **E3 corrected.** The equal 0.198 / 0.0198 first-update address statistic is a SUM of per-tensor norms (concatenated ≈ 0.142 for A0). Parameter count plus Adam explains the equality across layers. It is not a measurement of coordinate motion.
4. **F3a corrected.** An absent-mass auxiliary loss is ALSO flat once every positive-weight stencil cell is absent (the weights sum to 1). It can only resist exits while the read still overlaps occupied cells; it cannot recover an escaped read. Recovery needs a distance/anchor signal (e.g. pull toward the nearest occupied cell) or an occupied-cell fallback. Renormalizing over occupied cells alone also cannot recover a fully absent read.
5. **F2 corrected.** Lowering or warming only the AddressMLP lr does not freeze routing, because the q/k projections still change its inputs. The candidate must address q_proj, k_proj and AddressMLP, or separate routing projections from content projections. Earlier adapters can also change z, so freezing these three groups alone does not guarantee fixed coordinates; any strict routing freeze must specify its feature path too.
6. **F1 rationale corrected.** PKM's top-k always selects existing trainable slots; its low coverage is not our absent-cell lookup. Our q/k are already L2-normalized, so the relevant variant is removing the SHARED DIRECTION (centering/whitening the routing inputs), not normalization as such. PKM stays an analogy, not precedent for this exact failure.
7. **A2 is not a certified ceiling.** A constant address map also gives zero supervised pair loss. A2 is still NOT RUN.
8. Keep **retention** (reads stay on occupied cells) distinct from **useful retrieval**. One failed fix would not prove the design dead.

User 22058: "leave the GPU alone, do further research first". This note uses saved Stage A / diagnosis telemetry, CPU mathematical examples and literature. No new backbone forward, optimizer step, training, GPU workload or paid run. Observations, exact local gradient statements and untested causal hypotheses are distinguished below.

## Our evidence
| # | observation | source |
|---|---|---|
| E1 | At reconstructed init, Qwen reads land on allocated cells (absent ≤ .13) and overlap the bound writes about as much as the toy's do | diagnosis fa0e44d |
| E2 | lr 3e-3: absent 4.7% → 99.6% by update 25. lr 3e-4 (A1): 48.9% at 25, 65.2% at 100 (dose-response with step size) | Stage A a25f79a |
| E3 | Update 0's SUM of per-tensor address-MLP update norms is approximately 0.19795 (A0) or 0.019795 (A1) in each layer. Parameter counts and Adam's near-sign first step explain the scale; tiny/zero gradients are exceptions. This is not coordinate displacement. The toy has different parameter counts, so its 0.093 statistic is not a matched comparison | A0/A1/P2C telemetry; codex CPU arithmetic |
| E4 | Qwen query vectors are more similar at init (layer-mean pairwise cos .53–.72); the toy's layer means are .005–.043 | diagnosis |
| E5 | After the escape, the read spread grows 0.97 → 3.7–3.8 cells (A0) or 1.6–1.8 (A1) while the reads sit off the memory | Stage A dev evals |
| E6 | A1 train loss falls below ln 64 (4.23 → 3.85 by update 90; batch acc 9%) while dev stays at chance. Phase-1 training has filler 0, leaving recent bindings inside the local window. A context shortcut is a hypothesis: the taskhead has no direct residual bypass, so any such influence must pass through nonzero read features. The cause of the train/dev gap is unmeasured | Stage A; taskhead wiring |

## Mechanism (ranked; untested)
- **M1. Differential motion of concentrated query/key populations** (compatible with E2–E4, not established).
  - Similar inputs may respond similarly to parameter updates. Reads and writes can still respond differently because q/k projections and AddressMLP Jacobians differ between their populations.
  - The direction and magnitude of that difference have not been measured. Adam update norms and within-query cosine alone do not determine them.
  - A1's lower GLOBAL lr slowed escape on one seed, but also changed content/head learning; it does not isolate an address optimizer effect.
  - The toy comparison is confounded by backbone, dimensions and feature shift. It suggests a diagnostic direction, not immunity to this failure.
- **M2. Suppressing unhelpful reads may reduce early loss** (conditional).
  - Convex cross-entropy favors suppressing conditionally zero-mean logit noise. Whether the actual learned reads satisfy that assumption is untested; near-zero mean q·bound-k does not establish absence of useful information.
  - Suppression can act through head/v/β/content alignment or spatial support. M2 does not uniquely predict spatial escape or negative q·k.
  - All-zero taskhead features give head-bias-only logits, not necessarily uniform logits. Loss approaching ln 64 is compatible with suppression, not proof of its mechanism.
- **Compact-support trap** (exact local code property). A fully absent stencil supplies zero local read-path gradient. Other examples, layers, shared parameters and Adam momentum can still move the full system; ~99% pooled dev absence does not establish an absorbing training state. The trainer's AdamW weight_decay is 0.

## Related literature and limits of the analogies
- **Product-key memory** ([Lample et al. 2019, sections 3.1/4.5](https://proceedings.neurips.cc/paper/2019/file/9d8df73a3cfbf3c5b47bc9b50f214aff-Paper.pdf)): query BatchNorm improved coverage from 25.8% to 80.3% at 1M slots, with better perplexity. Its top-k selects existing trainable slots; our stencil can select no allocated cells. This supports a query-conditioning candidate, not a demonstrated cure for our failure.
- **VQ codebook collapse:** unused codevectors can lose useful training signals. Data-based initialization/re-initialization and encoded-feature anchors have improved codebook utilization in [Online Clustered Codebook](https://arxiv.org/abs/2307.15139v1) and [Łańcucki et al. 2020](https://arxiv.org/abs/2005.08520v1). Their interventions move/reinitialize codevectors; adapting this idea to episodic sparse banks changes the algorithm. An all-absent stencil is an analogy, not the same failure.
- **Anisotropy / massive activations:** [Sun et al. 2024](https://arxiv.org/abs/2402.17762v1) and [Roh et al. 2026](https://arxiv.org/abs/2603.00029v1) report concentrated activations/representations in LMs. Our saved geometry establishes higher query similarity for this Qwen setup than this toy. It does not measure massive activations, show that the toy lacks them, or establish their causal role. Removing a shared direction could also discard useful information.

## Fix candidates (unsupervised unless marked; ranked by evidence × cost)
| fix | targets | closest precedent | one cheap test |
|---|---|---|---|
| F1 center/condition routing inputs using permitted training/source data, with evaluation behavior specified | M1 | PKM analogy | Inspect differential sensitivity first; future matched screen checks retention AND useful retrieval |
| F2 stabilize the routing path, including q/k projections, AddressMLP and a specified upstream feature path; or separate routing/content projections | M1, content/routing interference | bootstrap hypothesis | Measure parameter-group contributions to read-vs-write motion before selecting the intervention |
| F3 (a) absent-mass penalty while overlap survives; (b) distance/anchor signal or occupied fallback for fully escaped reads | compact-support trap | VQ anchor/reset analogy | CPU far-empty gradient check already distinguishes prevention from recovery; future model screen must also check discrimination |
| F4 data-dependent address initialization on permitted training/source features, e.g. PCA / k-means | initial geometry | VQ initialization analogy | Check initial support and binding collisions; a future training screen would test persistence |
| F5 a design change: content-based top-k over occupied cells (never empty) instead of a spatial stencil | trap | PKM, Memorizing Transformers | a separate design track |
| A2 privileged supervised pair matching, still NOT RUN; constant maps achieve zero pair loss | alignment diagnostic, not a certified ceiling | — | Only in a separately authorized scope; pair loss/retention alone cannot certify retrieval |

**Proposed next diagnostic, not execution authorization.** Measure differential read/write motion over early updates, separating direct AddressMLP changes, q/k projection changes and upstream feature changes. The saved snapshots do not provide every update from 0–25; obtaining that trajectory requires new bounded training or exact optimizer replay unless the requisite checkpoints already exist. Model forwards and training remain outside the current CPU-reading scope, even if a later local run has no cloud charge.

Use that measurement to choose one matched intervention if causal attribution is the goal. A combined F1+F2 test would test the bundle, not identify which mechanism helped. Do not automatically escalate to another variant, A2 or a redesign after a failed screen. Future scope, limits and launch review must be concrete before any run.

Retained occupied reads are a guard against this failure, not proof of useful retrieval or a criterion separating a fixable design from one requiring replacement. Learning claims still need held-out task improvement and memory/address interventions. Train loss alone does not establish memory learning.

## Unresolved
- The block-shift size per early step was not measured (it needs a Qwen forward; CPU is possible but RAM is tight while smollm runs).
- Whether M2 is needed at all, or M1 alone suffices.
- The cause of A2's missing GPU and of the 12.7-min scheduling gap.
