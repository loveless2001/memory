# M4-SGM on frozen Qwen3-0.6B — closing write-up r3 (P2.5 → B2 → CPU diagnosis)

r3 supersedes r1 (22360) and r2 (22363), both kept unchanged; r2 applied codex 22362, r3 applies codex 22364.

Status: **CLOSED 2026-10-10 by the user** (#gravity 22357, "stop and write up then clean up").
Scope: the frozen-Qwen3-0.6B-Base sidecar line only (P2.5 onward). The scratch-model P0–P2C record stays in [M4-SGM.md](../../M4-SGM.md).
Roles: claude implemented and ran; codex audited every package and terminal result.

## Plain summary
- We attached the SGM memory sidecar (sparse 2D-addressed delta-rule cells at layers 6/13/20/27) to frozen Qwen3-0.6B-Base. We then trained it on the synthetic key→value binding task that the scratch model had learned with memory (P2C: N32 60.5/64.9%, memory-use pass).
- **On Qwen, no learned-routing (non-oracle) recipe demonstrated memory use.** The oracle-routing controls are not negatives: they reached 100/97.9% at N32. The baseline recipe's reads drifted off the stored cells within the first ~100 updates. A variant that kept reads on stored cells (fill+anchor) trained for 1,500 updates, and the memory ended up suppressed instead of used.
- **Scope of the negative:** this sidecar design and these recipes, on frozen Qwen3-0.6B. Most runs used one seed; the P2.5 screen used two. It is not evidence that a frozen pretrained model cannot use a memory.

## Results by stage (numbers as registered; 64-way task, chance 1/64 = 16/1024)
| Stage | What | Result | Cost (provisional) |
|---|---|---|---|
| P2.5 prep | L40S profile, exact-math speed-up (bitwise parity), re-timing, A100 packing test, packed-slot proof | usable/PASS; speed-up 1.44–1.46×; packing 1.93× (k=2); proof bitwise PASS | $0.31 + $0.76 + $0.24 + $0.31 + $2.92 |
| P2.5 screen (2026-10-07) | 18 cells, A100 packed, P2C curriculum, residual head, N16/N32 × 2 seeds | **SCREEN NOT PASSED at N32 and N16; memory_use FALSE.** Reserved acc N32: oracle 100/97.9%, learned 6.9/5.9% (71/1024, 60/1024), single-cell 8.6/6.0, random-fixed 12.5/8.9, memory-off 1.5/1.9. N16: learned 3.9/2.1 vs random-fixed 8.2/1.7. Reading is post-hoc amended (learned-n32-s1 null grad_norm leaves; original reading "unavailable" kept). Codex: recipe-transfer failure, not a tiny-model capacity wall | $126.44 |
| Saved-evidence diagnosis ($0) | retained telemetry | curriculum phase 1 is solvable without memory under the residual head (memory-off train acc 90% N16 / 42% N32). Gates non-selective; β grads ~1e-5 (P2C .08–.5) | $0 |
| Readout probe | taskhead (memory-read features only), learned N32 × 2 seeds | **NEGATIVE: rescue not shown.** Taskhead 12/1024, 16/1024 vs residual head 74/1024, 65/1024 on the same artifact population (−6.05/−4.79 pp). Constant-class predictions, loss ≈ ln64, empty-read weight ≈ 1 | $18.55 |
| Dead-start diagnosis ($0, local) | address geometry, init → step 100 | Not dead at init: reads land on allocated cells and get address gradient. By step 100, ≥.97 of read weight is on empty cells. Qwen q/k pairwise cos .5–.7 → .93–.96 (toy .01–.04). Only the local read-path gradient is zero after escape; "absorbing" not shown | $0 |
| Stage A (100 updates, L40S) | A0 baseline, A1 lr 3e-4, A2 address supervision | A0 escaped: absent 4.7% → 99.6% at update 25. A1 partial: 65.2% at 100 (lower lr delays, does not prevent). A2 NOT RUN (no container) | $0.92 |
| Research note r3 ($0) | mechanism + fix candidates | mechanism open. Candidates: centre/whiten address inputs, address-only lr warm-up, absent-read aux/reset, data-dependent address init, content top-k redesign | $0 |
| B1 fill+anchor (100 updates) | occupied-cell softmax fill τ1 + anchor λ0.1 (side branch) | Completed all 100 designed updates. Routing band **PARTIAL** (a routing-quality label, not unfinished execution): pre-fill absent weight .26 at 100 (A0 .993), band ≤.2 missed. Dev at chance; task CE ≈ ln64 | $0.71 |
| B2 fill+anchor (1,500 updates, seed 0) | same, held-out memory-use gate (≥12/256 AND drop ≥6 under bank derange) | **VALID_NEGATIVE:** 5/256 normal = 5/256 deranged (chance ≈ 4). Dev 9→5 over 0–1500; task CE ≈ ln64. Empty-read weight in band 300–1200, then .22–.24 | $10.92 |
| CPU gradient-path diagnosis ($0) | task-CE vs anchor grads, retrieval geometry at B2 init / B2 final / oracle-init | **COMPLETE, diagnostic only.** Init: task CE reaches q/k/value/β/address at all 4 layers + head; only L27 out_proj/alpha None (unused by design). B2 final: writes suppressed at L6/L13 (β .0005/.006 vs .55/.45), read norms ~0, projected value-token k/v near-collinear (cos .95–.98 / .89–.92), address routing at chance. Task value grads at L13/20/27 ~18,000×/4,300×/660,000× below init | $0 |

**Total about $162, provisional**: the sum of per-stage billing snapshots, some of which are only known to the cent or less precisely, so no cent-level total is claimed. It is provisional, not a settled invoice. The P2.5 attempt-1 image build is unattributed, and the probe and campaign await settlement.

## What is established vs open
- Established: (1) frozen-Qwen sidecar reads escape to empty cells under the baseline recipe, early in training. (2) With reads held on stored cells (fill+anchor), 1,500 updates give no demonstrated memory use for that variant, seed and recipe. (3) The direct task→read→write gradient path is open at init. (4) At the B2 endpoint the memory is suppressed.
- Not established:
  - Why escape or suppression happens. H1 noisy-read escape and H2 block shift of anisotropic reads are both untested.
  - Whether weak reads caused the suppression, or when it happened. Only endpoint measurements exist; the step-750 checkpoint is retained but its geometry was not run.
  - Whether centring/whitening (q/k are already L2-normalised), anti-collapse terms or a content top-k redesign would work.
  - Per-example B2 outputs were not saved, so equal 5/256 counts don't show identical predictions.

## Lessons kept
- Phase-1 curriculum + residual head admits a no-memory route. A readout must force memory dependence before memory-use claims mean anything.
- On this box (6.8 GB RAM WSL): local CPU/GPU probes run only under a cgroup cap (`systemd-run --user --scope -p MemoryMax=…`). Smoke at least 2 batches. r1 of the CPU probe was killed by a global OOM (kernel log), and WSL shut down ~1.5 min later; the shutdown trigger is unknown.
- Deployed-app cleanup needs `modal app stop --yes`. The B2 resume runner line 465 still lacks it, so fix it, add a real CLI regression test and get codex review before any reuse.
- Verify hashes + ZIP CRC after every `modal volume get`; rc 0 ≠ intact.

## Evidence (main checkout `mvp` unless noted)
- P2.5 prereg/campaign: `plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/` (readings `…/p2p5-qwen3-0p6b-screen-v1/readings/volume-evidence/collect-1/readings-v1/readings.json` e8764c42; terminal `pk-campaign-terminal/terminal-package.md`)
- Saved-evidence diagnosis: `plans/reports/claude-261008-0127-p2p5-saved-evidence-diagnosis/`
- Probe: `plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/reading-v1/probe-reading.json`
- Dead-start diagnosis: `plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/`
- Stage A: `plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/`; research note `plans/reports/claude-261009-0340-qwen-read-escape-mechanism-and-fix-candidates-research.md`
- Branch `m4-sgm-occupied-fill-v1` (worktree `../memory-occupied-fill-v1-worktree`, head ebc0030):
  - B1: `plans/261009-1040-…/b1-run-v1-readout-r2.md`
  - B2: `plans/261009-1135-…/b2-final-readout.md`
  - CPU diagnosis: `plans/261009-2209-m4-sgm-b2-cpu-gradient-path-diagnosis/r3-b1-k16/r3-readout-r3.md` (r1/r2 kept)
- Codex terminal audits (`plans/reports/`): campaign readings `codex-261007-p2p5-pk-21729-terminal-readings-audit`, Stage A `codex-261009-gravity-22049-stage-a-terminal-audit`, B1 `codex-261009-gravity-wait36-b1-terminal-audit`, B2 `codex-261009-gravity-wait42-b2-resume-terminal-audit`, CPU probe `codex-261010-gravity-wait49-cpu-probe-terminal-audit`; probe terminal audit = #gravity 21925.

## Unresolved questions
- Settled billing for the campaign/probe/B2 (all figures provisional).
- Merge the side branch `m4-sgm-occupied-fill-v1` into `mvp`, or keep it separate? It is kept separate today because closed-campaign tests bind the mvp memsub source.

## r2 changes (codex 22362)
- Plain summary narrowed to learned-routing/non-oracle recipes; oracle controls are not negatives.
- r1 CPU-probe crash wording = verified global OOM kill + WSL shutdown with unknown trigger.

## r3 changes (codex 22364)
- B1: completed 100 designed updates; PARTIAL = routing-quality band.
- Total stated as about $162 provisional (rounded stage costs sum to 162.08; no cent precision claimed).
