# Independent address-gradient review

Scope: user #gravity 22058/22059; CPU arithmetic on existing JSONs, code reading, primary literature and fixed mathematical examples. No Qwen/toy backbone load or forward, sampled task episodes, optimizer, training, GPU call or paid run. The earlier geometry clearance and re-arm request are superseded by the user's instruction to leave the GPU alone. The waiter gate patch was subsequently committed unarmed in caac2d7; this review does not authorize starting it.

**Conclusion:** escaping from unhelpful reads is mathematically possible, and an entirely empty stencil really does remove the local restoring gradient. Neither the delta rule nor high query cosine establishes that escape must happen. The most defensible working hypothesis is a combination of early read/content optimization, movement of the learned routing function, and a compact-support gradient trap. Its causal ordering remains unmeasured.

`cpu-examples.py` completed with exit 0 using CPU Torch 2.7.1+cpu, one thread, seed 0. `cpu-results.json` records source/input SHA256s and all numbers below. These are counterexamples and exact small calculations, not learning results or new model measurements.

## 1. What the implemented gradient says

The actual kernels are `memsub/sgm/delta_memory.py:19` and `:24`. For cell c, column-vector q/k/v and a key-by-value state S:

\[
r=\sum_c w_c(a_r)S_c^Tq,\qquad
S_c'=S_c+\beta w_c(a_w)k(v-S_c^Tk)^T.
\]

For fixed cell contents and q, with g=∂L/∂r,

\[
\frac{\partial L}{\partial a_r}
=\sum_c \nabla w_c(a_r)\,[g^TS_c^Tq].
\]

There is no fixed outward sign. For a previously zero bank and one write, define the spatial coupling K(a_r,a_w)=Σc w_c(a_r)w_c(a_w), treating weights outside a stencil as zero. Then

\[
r=\beta(q^Tk)vK(a_r,a_w),\qquad
\frac{\partial L}{\partial a_r}
=\beta(q^Tk)(g^Tv)\nabla_{a_r}K.
\]

Both content alignment and the classifier/target determine attraction versus repulsion. The write-side local derivative has the same absence of a universal sign. In the complete runtime, later writes, shared parameters and earlier read injections add further paths; this one-write formula is an explanatory special case, not a replacement for full-gradient ingestion.

Using the real delta kernel, B-spline and sparse bank, a write at (0,0), read at (0.6,0), β=0.5, q=k=1 and binary logits [r,0] with target 0 gives:

| Written value | Read | CE loss | ∂L/∂read-x | Gradient-descent direction |
|---|---:|---:|---:|---|
| +4, helpful | +0.448281 | 0.493919 | +0.266139 | toward the write |
| −4, harmful | −0.448281 | 0.942200 | −0.416673 | away from the write |

The delta update is error correction within each selected cell. For unit k, its post-write prediction for k is `(1−βw) Sᵀk + βw v`; it is not intrinsically an address repulsion rule. This distinction matches the fast-weight delta-rule formulation in [Schlag, Irie and Schmidhuber, ICML 2021, equations 20–25](https://proceedings.mlr.press/v139/schlag21a/schlag21a.pdf).

## 2. Noise avoidance is a conditional explanation

Cross-entropy is convex in logits. If a memory contribution ε is conditionally zero mean given a fixed target and baseline logits b, Jensen gives E[CE(b+ε,y)] ≥ CE(b,y). For fixed b and a fixed noise distribution, the expected loss along a nonnegative amplitude multiplier is minimized at zero and is nondecreasing away from zero. This establishes a way noisy reads could be suppressed; it does not establish that our reads satisfy these assumptions.

The fixed two-point example with logits [γ,0] and [−γ,0], each equally likely and the same target, gives expected CE 0.693147 at γ=0, 0.813262 at γ=1 and 1.126928 at γ=2. The derivative at γ=1 is +0.231059. No optimizer is involved.

Three limitations matter:

- Our bank states and head are learned together and may contain target-correlated signal. Near-zero mean `q·bound-k` alone does not establish useless information: other writes, residuals, heads and layers contribute.
- Attenuation can occur through the task head, v, β or content alignment as well as spatial escape. The noise argument does not select spatial escape over those alternatives, and does not explain a preference for negative rather than zero q·k under symmetric noise.
- All-zero taskhead features produce the head bias, not necessarily uniform logits. The code uses a biased `nn.Linear` and concatenates raw reads from every selected layer (`synthetic_pilot.py:125`, `synthetic_pilot_evaluation.py:48`). A local-context explanation for A1's improving train loss is plausible only through nonzero/context-dependent read features; there is no direct residual-to-taskhead bypass.

## 3. The empty-stencil trap is real; an empty-mass penalty shares it

The stencil uses detached integer indices and differentiable quadratic weights (`interpolation.py:30`). Missing cells contribute constant zero and reads do not allocate (`sparse_cell_bank.py:77`; runtime read at `sgm_model_runtime.py:165`). If every positive-weight cell in a stencil is absent, r=0 and this lookup's local gradients to its read address, q and stored writes vanish. The CPU example at (10,10) confirms zero address gradient; unused writes have no graph path and return None.

Let `A(a)=Σc w_c(a) 1[cell c absent]`. When all cells are absent, A=Σc w_c=1, hence ∇A=0 too. The example confirms exactly zero gradient. At a partially overlapping read at (1.4,0), absent mass is 0.405 and its x derivative is 0.9: such a penalty can discourage an exit while overlap survives. It cannot recover a fully escaped stencil by itself. Renormalizing over the occupied stencil cells likewise does not create support when the denominator is zero.

A squared distance to an occupied coordinate does supply a gradient outside the stencil: the fixed example's gradient at (10,10) relative to (0,0) is (20,20). An occupied-cell fallback or reset also changes the forward support. Those are distinct mechanisms, with allocation/search cost and discrimination tradeoffs; none has been run here.

This is a local graph statement. The observed ~99% average absent mass is not proof that all training reads are absent, or that the whole system is absorbing. Other examples, layers, shared parameters and Adam momentum can still move it. AdamW is configured with weight_decay=0.0 in this trainer.

## 4. What Adam and feature similarity establish

The saved A0/A1 telemetry confirms first-update address-MLP numbers near 0.19795 and 0.019795. But `synthetic_pilot.py:220` logs the **sum of per-tensor Euclidean norms**, not the Euclidean norm of a concatenated parameter vector. With Qwen's 32→64→2 MLP and ideal non-negligible first-step gradients, that sum is

\[
\eta(\sqrt{2048}+\sqrt{64}+\sqrt{128}+\sqrt{2})
=0.197948\quad(\eta=0.003).
\]

The corresponding concatenated norm is 0.142049. Approximate equality across layers follows from Adam's first-step magnitude and parameter counts. It is not a measured coordinate displacement or evidence of a common displacement direction. The first step is `−η g/(|g|+ε)` with bias correction; tiny/zero gradients are exceptions.

At fixed input features, changing the final shared AddressMLP bias moves read and write coordinates identically. In the CPU example, differential-coordinate change is at most 5.96e−8 (roundoff). Common translation can change B-spline lattice phase, but it cannot directly create a growing read/write centroid difference at fixed features.

What needs explaining is differential motion:

\[
\delta(a_r-a_w)\approx
[J_\theta\psi(q)-J_\theta\psi(k)]\delta\theta
+J_q\psi(q)\delta q-J_k\psi(k)\delta k,
\]

with additional changes in backbone features from upstream adapters. High within-query cosine can encourage similar responses among queries; it says little about these read-versus-write differences without the update direction/Jacobians.

An implementation consequence: **freezing only AddressMLP does not freeze routing**, because q_proj and k_proj remain trainable and feed the map. The `random_fixed` arm detaches q/k on that path but their projections still change from content gradients across updates. A routing warm-up must specify all changing inputs, or use separate routing projections; simply lowering the address-MLP learning rate leaves this indirect path active.

## 5. What the saved evidence supports

CPU aggregation across heads of the already saved diagnosis JSONs:

| Reconstructed init | q pairwise cosine | q·bound-k | Absent read mass |
|---|---:|---:|---:|
| Qwen taskhead seed 0 | 0.6194 | 0.0028 | 0.04670 |
| Qwen taskhead seed 1 | 0.6197 | 0.0120 | 0.04172 |
| Toy seed 0 | 0.0330 | −0.0090 | 0.00071 |
| Toy seed 1 | 0.0139 | 0.0248 | 0.00176 |

This verifies a similarity difference on this population, not its cause or causal effect. Width, depth, feature shift and initialization calibration also differ. It does not prove the toy lacks massive activations, nor that they drive the failure. The successful oracle snapshot has high within-query cosine too (head mean 0.9681); it bypasses learned addressing, so it is not a controlled learned-router test, but high cosine alone is not a universal memory-failure criterion.

Stage A's A0 absent mass is 0.99605 at 25 updates and 0.99275 at 100. A1's is 0.48867 and 0.65234. Thus the changed global learning rate materially changes the observed trajectory on this one seed. It does not isolate address optimization, and A1 has not demonstrated retention through 100. A2 has no result and remains NOT RUN / UNEVALUABLE. The earlier residual-head learned run retains occupied reads (head-mean absent mass 0.56117); do not claim every Qwen run has the same all-empty failure.

## 6. Literature and missing fix families

[Product-key memory, Lample et al., NeurIPS 2019, sections 3.1 and 4.5](https://proceedings.neurips.cc/paper/2019/file/9d8df73a3cfbf3c5b47bc9b50f214aff-Paper.pdf) supports query normalization as a candidate: at 1M slots, query BatchNorm improved coverage from 25.8% to 80.3% and perplexity from 19.8 to 18.0. Its top-k selects existing trainable key/value entries and normalizes their scores. Low coverage there means uneven use of available entries, unlike our ability to select no allocated cells. This is an analogy for geometry/utilization, not a demonstrated cure for our empty-stencil trap. The paper also gives memory values a higher optimizer rate than query/key parameters; episodic delta states in our system are not optimizer parameters, so copying that rule literally would be inappropriate.

[Gated DeltaNet, Yang, Kautz and Hatamizadeh, ICLR 2025, section 3.4 and Table S.2](https://arxiv.org/html/2412.06464v3) adds short convolution, L2-normalized q/k, output normalization and gating. Our q/k already receive L2 normalization. Their ablations motivate investigating content/write conditioning separately from routing; they do not show that adding another normalization fixes spatial support. Their memory has no learned sparse spatial stencil of our kind.

The following ranking orders diagnostic value and fit to the observed failure, not expected accuracy. Proposed future model tests need a separately reviewed scope and user authorization; nothing here launches or preregisters one.

| Priority / family | What it would address | Cheapest discriminating check |
|---|---|---|
| 1. Preserve or recover occupied support with an explicit distance/anchor signal or occupied-cell fallback | Proven local gradient trap; can act when the read is already fully empty | CPU far-empty gradient check completed here. A future matched short screen must test useful binding discrimination as well as retention, since routing every query to one cell can look healthy on absent mass |
| 2. Stabilize the entire routing path during content/head bootstrapping, or separate routing and content projections | Rapid movement before useful content is learned, including indirect q/k motion | Record same-feature coordinate changes from each updated parameter group, then compare a single routing-stabilization intervention. No such replay/forward was performed here |
| 3. Causal feature centering/calibration on permitted training/source data, with controlled routing rates | Verified Qwen/toy similarity difference; plausible coherent sensitivity | First inspect mean/variance and differential routing Jacobians on training features, without evaluation-data calibration. A new screen should change one registered factor if causal attribution is the aim |
| 4. Content/readout conditioning or a delayed routing schedule | Conditional noise-suppression incentive rather than spatial geometry alone | Decompose loss changes from read attenuation versus feature/head learning on fixed permitted episodes; an initial noisy read is not by itself evidence of useless content |

Supervised pair matching remains a diagnostic option, not an established ceiling. The existing AddressMLP-only squared pair loss admits a constant address function with exactly zero loss (CPU example completed). It therefore cannot certify discriminative addressing, capacity or successful task learning. Additional contrastive/dispersion constraints would change its objective and can introduce new tradeoffs.

Retention is a necessary guard for this failure mode, not a sufficient learning result. Likewise, failure of one normalization/warm-up combination, or failure of A2 if later authorized, would not establish that the whole design requires replacement. A valid learned-memory claim still needs held-out task improvement and appropriate memory/address interventions.

## Reconciliation requested

For Claude's research note: retain M1/M2 as conditional compatible hypotheses; distinguish measured absence from causal direction; qualify the Adam norm; distinguish PKM coverage from absent-cell support; replace absent-mass-only restoration with a signal that has nonzero far-empty gradient; include q/k motion in any routing warm-up; preserve A2's untested status and the user's GPU stop. Keep this independent artifact separate from frozen experimental reports.
