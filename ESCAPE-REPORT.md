# ESCAPE-REPORT.md — Unfreezing the Position Pathway

Pilot for the frozen-kernel mechanism (FULLRECIPE Q1(c): argmax kernel
bitwise frozen at init at every scale). Pre-registered hypothesis:
**logit-scale-induced gradient saturation** — d_l = 256 on QK-normed cosine
logits makes the position-dominated init one-hot from step 0, and a
saturated softmax passes ~zero gradient to the routing pathway while the
value/output path trains normally.

Status: **COMPLETE** (2026-07-20). D1 CONFIRMED (saturation mechanism,
ratio table below) · D2 ESCAPE DEMONSTRATED by E1 (√d_l) — 3-seed stable,
entropy 0.82→1.11, kernel Jaccard →0.18, loss 0.219 < frozen 0.365, y+
0.239 < 0.370 — and independently by E2 (learned temperature) · E3/E4 do
not escape (noise inert; content-seed off-floor but flat and
quality-catastrophic) · R3: no F1-flip (d_min ~0.50 even under a mobile
kernel). Selected arm (P0.2 of E1FULL): **E1 fixed √d_l**. Spend ≈ $95.

---

## P0 — G1/G2 gradient forensics (verdict first: **D1 CONFIRMED**)

One accumulated forward+backward of the corrected KL at init over the
fixed 128-item probe batch; grad L2 norms summed over 36 layers
(`escape/g1g2-gradient-table.json`; per-layer table in the artifact):

| group | G1 (canonical d_l=256) | G2 (scale √d_l=16, same weights) | G2/G1 |
|---|---|---|---|
| cross1 W_Q (+anchor) | **1.10e-11** | 5.49e-2 | **5.0e+9** |
| cross1 W_K (+anchor) | **1.61e-10** | 5.44e-1 | **3.4e+9** |
| latent banks | 6.13e-2 | 1.15e-1 | 1.9 |
| cross1 W_V | 21.6 | 76.2 | 3.5 |
| cross1 W_O | 21.6 | 76.2 | 3.5 |
| cross2 (all) | 21.6 | 76.2 | 3.5 |
| self-attn (all) | 17.3 | 61.1 | 3.5 |
| output heads (W_key, W_val) | 21.6 | 76.2 | 3.5 |
| init loss | 0.705 | 0.862 | — |

- **G1: the routing projections are numerically dead at init** — W_Q/W_K
  gradients sit 11–12 orders of magnitude below the healthy value path,
  exactly as predicted. (The latent banks show a small nonzero gradient:
  they also feed the residual/value stream and the output heads, so their
  gradient is not purely routing — the clean routing-only weights are
  W_Q/W_K.)
- **G2: swapping ONLY the logit scale to √d_l wakes the routing gradients
  by ~10 orders of magnitude** (value-path groups move only ×3.5, the
  generic effect of a softer softmax). Per D1, the saturation hypothesis
  is confirmed at the gradient level regardless of training outcomes.
- Cost of the softer softmax at init: identity passthrough degrades
  (loss 0.705 → 0.862) — kernel leakage the d_l scale was designed to
  suppress. E1 therefore starts from a worse loss; relevant to R5.

## Arms — R1–R5 readouts

All arms: mid-scale (9,498 items, 188 steps, true batch 32), canonical
config except the single lever; I1 every 25 steps; E0 = FULLRECIPE mid run
(reused, $0).

### R1 — entropy-vs-step (nats, mean over 36 layers)

| step | E0 canonical | E1 scale √d_l | E2 learned temp | E3 anchor noise | E4 content-seed |
|---|---|---|---|---|---|
| 0 | 1.16e-10 | 0.815 | 0.815 | 1.16e-10 | 0.539 |
| 50 | 1.16e-10 | 0.796 | (rerun) | 0.000000 | 0.546 |
| 100 | 1.16e-10 | 0.894 | | 0.000000 | 0.549 |
| 150 | 1.16e-10 | 1.019 | | 0.000000 | 0.543 |
| 188 | 1.16e-10 | **1.113** | | 0.000000 | 0.539 |

- **E1: DEPARTS AND RISES.** First departure beyond 10× floor is at
  step 0 by the lever (0.815 — √d_l is simply not saturated); the
  training-driven signature is the RISE from step ~75 onward
  (0.82 → 1.11) plus the kept-set explosion (layer-0 argmax positions
  1024 → 5,992 by step 188): routing is learning.
- E3: bitwise floor throughout — σ=0.02 anchor noise does NOT break
  saturation at d_l=256. Rules out "symmetric tie-breaking failure";
  the mechanism is saturation.
- E4: off-floor at init by construction (0.539) but FLAT through
  training — content in the pathway does not un-saturate most rows at
  d_l=256; loss pays heavily for the broken identity init (below).
- E2 OOM'd on first launch (the grad-requiring temperature scalar made
  autograd save the full [t×S] logit tensor per layer; fixed by folding
  the scale into q before the matmul) — rerun in flight.

### R2 — kernel mobility (Jaccard of kept sets vs step 0)

| step | E1 (l0 / mean36) | E3 | E4 (l0 / mean36) |
|---|---|---|---|
| 50 | 1.000 / 0.949 | 1.000 | 0.732 / 0.993 |
| 100 | 0.298 / 0.356 | 1.000 | 0.696 / 0.992 |
| 150 | 0.174 / 0.202 | 1.000 | 0.668 / 0.991 |
| 188 | **0.171 / 0.183** | 1.000 | 0.652 / 0.990 |

E1's kernel MOVES (Jaccard → 0.18 as entropy rises — the two
signatures co-occur exactly as D2 requires). E3 frozen. E4: only
layer 0 and a few others drift; the mean stays 0.99 — partial-row
saturation persists at canonical scale.

### R5 — loss

| arm | init loss | final loss (188) | vs E0 0.365 |
|---|---|---|---|
| E1 | 0.737 | **0.219** | better (−0.146) |
| E3 | 0.576 | 0.362 | ≈ E0 (lever inert) |
| E4 | 5.889 | 0.586 | worse (+0.221) |

E1 starts worse (softer softmax leaks the identity passthrough) and ends
**substantially better than the canonical baseline** — at mid scale, the
unfrozen compactor out-trains the frozen one on the very objective that
froze it.

### R3 — d_min AUC per checkpoint (PER-ITEM kernels from I2 argmax capture)

| step | E1 | E3 | E4 |
|---|---|---|---|
| 47 | 0.507 | 0.511 | 0.508 |
| 94 | 0.502 | 0.513 | 0.500 |
| 141 | 0.505 | 0.511 | 0.502 |
| 188 | **0.503** | 0.513 | 0.502 |

**No F1-flip**: write-time geometry stays loss-blind (~0.50) even in the
escaped arm whose kernel is mobile, item-adaptive and head-diverse. The
internality claim survives its strongest test so far at mid scale.

### R4 — y+ on the I2 1k subsample (escape vs quality)

| step | E0 (frozen) | E1 | E3 | E4 |
|---|---|---|---|---|
| 47 | 0.409 | 0.402 | 0.401 | 0.726 |
| 94 | 0.379 | 0.334 | 0.394 | 0.687 |
| 141 | 0.375 | 0.252 | 0.373 | 0.671 |
| 188 | 0.370 | **0.239** | 0.368 | 0.614 |

The escaped kernel does not trade quality for mobility — it LOSES 35%
FEWER facts than the frozen baseline at the same step count (0.239 vs
0.370). Per D4 escape and quality are separate claims at 188 steps; here
they point the same way. (E4's content seeding is catastrophic for
quality: 0.614.)

### R6 — item-invariance (mean pairwise cross-item Jaccard, I1 snapshots)

| arm | step 0 | step 188 |
|---|---|---|
| E1 | 1.000 | **0.821** (mildly item-adaptive) |
| E3 | 1.000 | 1.000 |
| E4 | 0.864 | 0.678 |

### R7 — head divergence (pairwise Jaccard of per-head kept sets)

| arm | step 0 | step 188 |
|---|---|---|
| E1 | 1.000 | **0.199** — heads DESPECIALIZE from the shared lattice |
| E3 | 1.000 | 1.000 |
| E4 | 0.291 | 0.279 |

E1's escape is not one moving lattice: the 8 KV-heads diverge into
substantially different kept sets (cross-head J 0.20) while remaining
mostly item-invariant (cross-item J 0.82) — head-specialized, weakly
content-conditioned routing.

### E1 3-seed replication (D2 stability)

| seed | final loss | entropy @188 | kept-l0 @188 |
|---|---|---|---|
| 1234 | 0.219 | 1.113 | 5,992 |
| 51234 | 0.225 | 1.086 | 5,214 |
| 91234 | 0.214 | 1.005 | 5,077 |

Escape replicates on every seed (entropy rise, kernel mobility, loss
below the frozen baseline's 0.365).

Entropy overlay figure (all arms + seeds):
`plans/260719-2124-escape-unfreezing-position-pathway/entropy-overlay-all-arms.png`

### E2 — learned temperature (rerun; two harness fixes en route)

E2 escapes independently: entropy 0.815 → **1.042**, kept-l0 1024 → 6,173,
kernel Jaccard vs init at 188 = **0.172** (l0 0.165), final loss
**0.2104**. Two instructive failures before the clean run: (1) OOM —
multiplying the [t×S] logits by a grad-requiring scalar makes autograd
save the full logit tensor per layer (fixed by folding the scale into q);
(2) safetensors shared-tensor rejection — registering the per-layer
temperature on each attention submodule aliased it 5× in the state dict
(fixed via non-registering attribute references). Both fixes are in the
inner trainer.

## Decision-rule verdicts (verbatim from ESCAPE.md)

- **D1 — CONFIRMED**: "G1 shows dead routing grads AND G2 wakes them →
  hypothesis CONFIRMED at the gradient level regardless of training
  outcomes; report the ratio table as the mechanism evidence." (Table
  above; W_Q ×5.0e9, W_K ×3.4e9.)
- **D2 — ESCAPE DEMONSTRATED** (E1, and independently E2): "any arm's
  entropy departs floor (R1) with Jaccard < 1.0 (R2) → ESCAPE
  DEMONSTRATED; that arm is the paper-#2 constructive result; run its
  3-seed replication; R3 on it answers the F1-flip question." E1
  replicated on 3 seeds; R3 answers the F1-flip question NEGATIVELY at
  mid scale — d_min AUC stays ~0.50 under a mobile, head-diverse,
  mildly item-adaptive kernel. Paper #2 §5 branch: internality holds
  even with content routing (subject to the full-scale retest, E1FULL
  Q3').
- **D3 — moot** (D2 fired). For the record: E3 (noise) stayed at floor
  with Jaccard 1.000 — saturation, not tie-breaking; E4 (content-seed)
  is off-floor by construction but flat, mostly frozen (mean J 0.99),
  and quality-catastrophic.
- **D4 — not triggered**: the escaped arm shows no quality regression;
  the opposite — y+ 0.239 vs 0.370 (35% fewer losses at 188 steps). Not
  a training claim; full-recipe verdicts belong to E1FULL.

## Arm selection (E1FULL P0.2, pre-registered rule applied)

D2-class arms: E1 (3-seed stable, final losses 0.214/0.219/0.225) and E2
(single seed, 0.2104). E2's loss sits inside E1's seed spread →
statistical tie → tie-break selects the SIMPLEST lever: **E1, fixed
logit scale √d_l = 16**. This config freezes into
compaction_policy_version material for the E1FULL run.

## Consequences for paper #2

- §2 (mechanism): the frozen kernel is init-time gradient saturation of
  the routing pathway — G1/G2 ratio table is the direct evidence; the
  FULLRECIPE "init fixed point" observation now has its cause.
- §5 (constructive): one hyperparameter (logit scale d_l → √d_l) unfreezes
  routing: entropy rises, heads despecialize (cross-head J 0.20), the
  kernel becomes mildly item-adaptive (cross-item J 0.82), loss and
  short-horizon quality BOTH improve. The Still recipe's d_l scale choice
  is load-bearing and, on this corpus/config, harmful.
- §5 branch (internality): even an escaped kernel's geometry is
  loss-blind (d_min ~0.50) at mid scale — the routable/unroutable
  asymmetry is not a frozen-kernel artifact so far. Full-scale retest in
  E1FULL.
- The entropy overlay figure is the candidate §5 opener.

## Cost ledger (actuals ≈)

G1/G2 $3 · E1/E3/E4 arms ~$10 ea · E2 ×3 attempts ~$14 · E1 seed
replications ~$20 · I2 sweeps (12 pts) ~$20 · R6/R7 $0 (existing
snapshots) · misc $3. **Total ≈ $95** (budget $130–185).

## Unresolved questions

- Whether √d_l remains stable to 1500+ steps at full data (E1FULL WP1).
- Whether item-adaptivity deepens with scale (R6 trajectory at full
  recipe — E1FULL Q1').
- The G1 latents-group gradient is small-but-alive at canonical scale
  (0.061) via its value-path role; a cleaner decomposition of latent
  gradient into routing vs value components was not attempted ($0 claim,
  not needed for D1).
