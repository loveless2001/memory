# FOLLOWUP-REPORT — Post-PROBE Micro-Experiments (F1/F2/F3)

Date: 2026-07-18 · Brief: /FOLLOWUP.md · Reference instance A =
`single-t1024-T8k`, target y_A (GT16 protocol), fixed capacity t=1024.
Eval: evicted-only, doc-level test split (sha256 bucket ≥ 0.7),
cluster-bootstrap 95% CIs (2,000 doc resamples). One GPU forward-pass run
(context-only, ~$8) + one CPU shard-extract; no training beyond the two
linear refits the brief allows. **Actual cost ≈ $9.**

**TL;DR — three verdicts, mutually reinforcing.** (F1) The shipped
compactor's cross-attention is a **stride-≈3 delta lattice**, head- and
item-invariant; its geometry is **loss-blind** — needle-to-lattice distance
predicts survival at chance (d_min AUC 0.509), the mechanics-with-kernel arm
reaches only 0.550 (+0.003 over c0). **Branch (iii): smear dominates.**
(F2) The read-side 0.85 is **answer-confidence, not memory-content readout**:
strip the question and the layer-30 residual goes to chance (refit 0.502,
zero-shot 0.508 vs question-conditioned 0.813) — the paper's claim downgrades
from "sufficiency readout" to **behavioral-divergence predictor**. (F3) The
middle deployment rung works: a **4-head sink/latent-mass monitor (8 scalars,
2 hooks, no capture infra) reaches 0.762** and gates end-to-end at lost 0.149
@ expand 0.060 — beside the full stack (0.146 @ 0.050), far inside the
refreshed gate (0.146 @ 0.147).

---

## F1 — Kernel-distance mechanics feature  [BLOCKING — decides §8's branch]

**The kept kernel, measured.** Hooking block-1 cross-attention of the first
compactor layer and reading per-latent argmax source positions on 5,090
test items: the kept set is `round(k·(S−1)/1023)`, k=0..1023 — a **uniform
stride-≈2.998 lattice** at the full source length S=3068 (density exactly
1/3). It is **identical across all 8 KV-heads and across all items** (item-to-
item diff = 0). This is the delta-position-kernel finding, now localized to
the sampled positions themselves: compaction keeps every ~3rd source token,
content-blind.

**Consequence for the feature.** Because any span of ≥3 contiguous source
tokens contains a lattice point, `d_min` for multi-token needles is ~always
0 and `frac_needle_kept` ~always 1/3; the only variation is the phase of the
answer token(s) relative to the lattice.

| quantity | value | 95% CI |
|---|---:|---|
| ⟨F1-uni⟩ d_min univariate AUC vs y_A | **0.509** | [0.499, 0.519] |
| d_mean univariate AUC | 0.504 | [0.486, 0.522] |
| frac_needle_kept univariate AUC | 0.504 | [0.485, 0.521] |
| c0 surface floor (this eval) | 0.547 | [0.534, 0.559] |
| kernel-features-only arm | 0.520 | [0.507, 0.532] |
| ⟨F1-arm⟩ **mechanics-with-kernel (c0+kernel)** | **0.550** | [0.537, 0.563] |
| Δ over c0 | +0.003 | — |
| ⟨F1-corr⟩ Spearman c2-score ↔ d_min | **0.045** | p=0.005 |

Needle localization uses the finest available metadata (`chunk_rel_start` +
`ans_rel_offset·span` from surface-features; char≈token ratio); 3,962 of
5,090 test items have a locatable in-prefix answer (77.8%). The c2↔d_min
correlation is statistically nonzero but negligibly small: **almost none of
the 0.85 is kernel geometry.**

**BRANCH SELECTION (verbatim):**
> **<0.60 → smear dominates; branch (iii).**

The fixed subsampling kernel routes by position, not content, and its
geometry does not decide which facts survive — leakage smear and downstream
computation do. Subsampling loss is **not** mechanics-routable from the
write-time kernel. (§8 keeps branch (iii): synthesis/subsampling loss routes
only through read-side computation, at 0.85 — and, per F2, that read-side
signal is answer-conditioned.)

## F2 — Context-only probe control  [BLOCKING — validity of the 0.85]

Re-forwarded the 5,090 test items with the **same compact context, no
question**, reading the layer-30 residual at the last context token (newline
sentinel). The question-conditioned layer-30 linear probe reproduces test
AUC 0.813 (sanity; matches c2_lin 0.819).

| readout | AUC | 95% CI |
|---|---:|---|
| ⟨F2-refit⟩ fresh probe on context-only states (doc 5-fold OOF) | **0.502** | [0.487, 0.518] |
| ⟨F2-zeroshot⟩ question-probe applied to context-only states | **0.508** | [0.493, 0.523] |
| question-conditioned probe (reference) | 0.813 | — |

**Reading.** Both are at chance. Strip the question and layer-30 carries
**no linearly-decodable sufficiency signal** — the sufficiency label is
question-specific, and the residual can only encode it once the model knows
which fact is being asked about. The c2 probe reads *"the model will not
answer as it would have with full context,"* i.e. **answer-confidence /
behavioral divergence**, not a question-independent memory-content readout.

**Claim downgrade (for the paper):** "sufficiency readout" → **"behavioral-
divergence predictor."** Still deployable — the question is present at gate
time, so the 0.85 stands as an operating signal — but the *sentence* changes:
the probe does not certify that the fact is in memory; it predicts that the
model's answer will diverge. This decisively resolves PROBE unresolved #1.

## F3 — Standalone sink-head monitor  [near-blocking — the middle rung]

From existing capture shards (step-0, last-prompt), the 4 inventory heads'
latent-mass + sink-mass — L25/H14, L26/H26, L28/H19, L35/H15 × {m_lat,
m_sink} = 8 scalars — logistic, train-fit, test eval.

| quantity | value | 95% CI |
|---|---:|---|
| ⟨F3-AUC⟩ sink-head monitor (8 scalars) | **0.762** | [0.753, 0.771] |
| per-domain | code 0.728 · fin 0.784 · legal 0.792 · lit 0.783 | |
| p2 + sink-heads combined | 0.763 | (p2 adds ~0) |
| ⟨F3-e2e⟩ p2+sink-heads gate, test | **lost 0.149 @ expand_all 0.060** | τ from val |

The monitor matches the capture-trained per-head probe (c1d 0.767) with
**two scalar hooks and no capture pipeline**, and its end-to-end point sits
essentially on the full stack's (0.146 @ 0.050), far inside the refreshed
gate (0.146 @ 0.147). **Deployment ladder completed:**

> p2 (free, 0.638) → **sink-heads (+2 hooks, 0.762)** → full stack (capture,
> 0.854).

---

## Consequences for the paper (§8)

1. **Branch (iii) confirmed with a mechanism.** The routability asymmetry's
   third clause is now sharp: subsampling loss does not route via the
   write-time kernel (F1: geometry loss-blind, 0.550) — it routes only via
   read-side computation (0.85), and (F2) that read-side signal is
   answer-conditioned, not a memory-content certificate.
2. **Downgrade the read-side claim** everywhere the paper says the probe
   "reads sufficiency" / "reads memory content": it predicts behavioral
   divergence under the question. Deployability is unchanged.
3. **Three-rung ladder is real** and cheap in the middle: sink-head mass
   (2 hooks) buys 0.762 / near-stack e2e without any capture infrastructure.

## Placeholder map (for `gate_paper_draft_v0.2.md`, not yet created)

| placeholder | value |
|---|---|
| ⟨F1-uni⟩ | 0.509 [0.499, 0.519] |
| ⟨F1-arm⟩ | 0.550 [0.537, 0.563] (+0.003 over c0) |
| ⟨F1-corr⟩ | ρ=0.045 (p=0.005) |
| F1 branch | (iii) smear dominates |
| ⟨F2-refit⟩ | 0.502 [0.487, 0.518] |
| ⟨F2-zeroshot⟩ | 0.508 [0.493, 0.523] |
| ⟨F3-AUC⟩ | 0.762 [0.753, 0.771] |
| ⟨F3-e2e⟩ | lost 0.149 @ expand 0.060 |

## Artifacts

- repo `plans/260718-0155-followup-f1f2f3/`: `analyze-followup-f1-f2-f3.py`,
  `f1-verdict.json`, `f2-verdict.json`, `f3-monitor.json`,
  `followup-all-verdicts.json`, `f1-kernel-features.npz`,
  `f2-context-only-states.npz`, per-slice captures, `pilot-slice-00.npz`
  (raw argmax kernel).
- Modal runners: `modal-followup-f1f2-context-only-and-kept-kernel.py`
  (GPU, context-only residual + kept kernel),
  `modal-followup-f3-headfeats-and-f2-zeroshot-probe.py` (CPU extract).
- `memsub-artifacts:/probe/`: `followup-f1f2-slice-{00..03}.npz`,
  `followup-f3-headfeats.npz`, `followup-f2-zeroshot-probe.npz`,
  `followup-f1-kernel-features.npz`, `followup-f2-context-only-states.npz`,
  `followup-f3-monitor.json`. Updated `arm-table.json` carries the three
  new rows (`f1_mechanics_with_kernel`, `f3_sinkheads`, `f2_context_only`)
  and `_followup_verdicts`.

## Deviations & assumptions

1. **Kept positions were not stored in the shipped shards** (the scaled
   PROBE run was `light=True`; c3a hooks were dropped). F1 recovers them by
   re-running block-1 cross-attention argmax in the F2 forward pass — exact
   per-item, no analytic assumption on the test set. The mechanics-with-
   kernel *arm* (needs train-split features) uses the analytic S=3068 lattice
   (item-invariant, verified against exact keepcount on test).
2. Needle localization is `chunk_rel_start + ans_rel_offset·1024` (char≈token
   ratio); the finest metadata available. 22.2% of test items lack a
   locatable in-prefix answer and are excluded from F1's needle features.
3. F2 reads at a newline sentinel after the compact context (operationalizes
   "last context token, no question"); same layer index (30) as c2 — the only
   difference from c2 is the absent question, which is the intended control.
4. F2/F1 ran on a doc-level subsample (frac=0.55, 5,090 of 9,230 test items,
   2,646 docs) to hold the ~$8 forward-pass budget; CIs reflect the sample.
5. GT22-style weighting for ⟨F3-e2e⟩ is identical to the PROBE GT22 harness
   (natural-prevalence weights over evicted rows; τ on val for lost ≤ 0.146;
   non-evicted rows never expanded, expand_all = expand_evicted × 0.832).

## Unresolved questions

1. Is the answer-confidence signal (F2) present *earlier* in the stack under
   the question, or does it also crystallize only at layer ~30? (Not run;
   F2 fixed layer 30 to isolate the question vs no-question contrast.)
2. Would a full-recipe compactor (past the position-kernel regime) make the
   kernel geometry loss-bearing — i.e. flip F1 to branch (i)/(ii)? The kept-
   kernel probe here should be re-run on any retrained compactor.
3. F2 downgrade is scoped to linear decodability at layer 30; a nonlinear or
   multi-layer context-only probe was not tried (out of brief scope).

Stop condition met: F1/F2/F3 resolved, branch (iii) selected, three
artifacts written, arm-table updated. No further arms.
