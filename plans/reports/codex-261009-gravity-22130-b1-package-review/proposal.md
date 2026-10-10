# B1 occupied-fill retention screen — proposal v0.1 (NOT launched)

User 22128 "go" after codex 22127 cleared the CPU implementation (1b01245) for preparing a bounded 100-update proposal. Launch needs: codex package clearance + user OK on the cap below + chat_read right before launch. GPU stop (22058) otherwise stands.

## Question
Under A0's exact recipe (where query reads escaped: original-stencil absent mass 0.047 → 0.993 by update 100), do Qwen query reads stay on the memory with `occupied_softmax_fill_v1` (fill + anchor)?

## Arm (one)
- B1 = Stage A A0 (probe s0 PilotConfig sha 4e89b95a…, checked against Stage A BASE_EXPECT; lr 3e-3, seed 0, batch 16, N32, taskhead, 100 updates all in the filler-0 phase, dev evals 0/25/50/75/100 on heldout seed 4242, 4×16) + `sgm = {read_fallback: occupied_softmax_fill_v1, read_fallback_tau: 1.0, read_fallback_anchor: 0.1}`. Nothing else differs (tested).
- Spec: `plans/261009-0945-m4-sgm-p2p5-occupied-cell-read-fallback-spec/spec.md`.
- Source: branch `m4-sgm-occupied-fill-v1` (this package commit); memsub sha d86639b9… (runner refuses any other local tree). Dev only: no final/intervention/train-split evals, no reserved seeds.

## Pre-registered readout (no thresholds tuned after)
Band = Stage A `classify()` unchanged, on `query_empty_read_weight` = ORIGINAL-stencil absent mass, measured BEFORE fill:

| result at update 100 | reading |
|---|---|
| kept (≤ 0.2) | anchor kept routing on the memory, this seed. Mechanics only, not retrieval. |
| escaped (≥ 0.9) and fully-absent fraction ≥ 0.5 | fill carries the reads; lookup changed; NOT retained routing |
| escaped, fully-absent < 0.5 / partial | reported as measured; no claim |
| INVALID / refused / timeout | no result; no retry |

Reported beside, never criteria: dev accuracy by step (chance 1/64), fully-absent fraction, nearest-occupied distance, fill support, `read_anchor` per logged step. 100 updates is a routing/mechanics gate, not designed to show retrieval.

## Stops
One launch. No retry, no relaunch on the used Dict, no 100→1500 continuation, no A2, no other arms. Any follow-up = new proposal + codex + user.

## Resources, deadline, cost
- Modal ephemeral `modal run` (not --detach), existing image im-A7BXMB8v1cVYRvC9pMqZ3i (no image construction), 1× L40S, 4 CPU, 32 GiB, retries 0, max_containers 1, scaledown 2 s.
- Child ≤ 1500 s (A0 child: 642 s), function 1560 s, startup 300 s, campaign deadline 2400 s from first call, client timeout 2610 s + 30 s kill. Server-side deadline killers as Stage A.
- **Expected ≈ $0.5–0.7** (A0 child 642 s × $0.000665/s ≈ $0.43 at listed base rates + load/startup + unprofiled fill overhead).
- **Reservation $1.99** = (client 2640 s + 300 s stop allowance) × $0.00067854/s (CPU priced +25%). **Cap asked: $2.50.** Unenforced: app-stop latency after client exit (cleanup-verify checks it). Billing provisional until Modal reports.
- A queue delay (Stage A A0 waited 12.7 min) eats campaign time; < 600 s left at entry → refusal, ≈ $0, no retry.
- Local RTX 3060 Laptop (6 GB): not proposed (fit unknown; user's GPU stop).

## Launch procedure (after both approvals)
1. `chat_read` #gravity; confirm worktree HEAD = audited commit, clean tree.
2. From `/home/lenovo/projects/memory-occupied-fill-v1-worktree`: `setsid nohup bash plans/261009-1040-m4-sgm-p2p5-b1-occupied-fill-retention-screen/launch-b1-once.sh > /dev/null 2>&1 < /dev/null &`
3. Watch console/exit; then cleanup-verify verdict, result readout, billing snapshot → #gravity; codex audits.

## Unresolved
- Fill overhead on GPU (gathers every occupied cell per query read; ingestion unchanged).
- λ = 0.1 / τ = 1 untuned; one seed only.
