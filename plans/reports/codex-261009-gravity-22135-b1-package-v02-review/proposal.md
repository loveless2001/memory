# B1 occupied-fill retention screen — proposal v0.2 (NOT launched)

v0.2 (codex 22132/22133 HOLD on v0.1 53cd307): cleanup bounded by ONE overall budget equal to the ledger's stop allowance; reservation labelled conditional with its assumptions; outcomes attributed to fill+anchor together; endpoint vs all-checkpoint support reported separately.

User 22128 "go" after codex 22127 cleared the CPU implementation (1b01245) for preparing a bounded 100-update proposal. Launch needs: codex package clearance + user OK on the cap below + chat_read right before launch. GPU stop (22058) otherwise stands.

## Question
Under A0's exact recipe (where query reads escaped: original-stencil absent mass 0.047 → 0.993 by update 100), do Qwen query reads stay on the memory with `occupied_softmax_fill_v1` (fill + anchor)?

## Arm (one)
- B1 = Stage A A0 (probe s0 PilotConfig sha 4e89b95a…, checked against Stage A BASE_EXPECT; lr 3e-3, seed 0, batch 16, N32, taskhead, 100 updates all in the filler-0 phase, dev evals 0/25/50/75/100 on heldout seed 4242, 4×16) + `sgm = {read_fallback: occupied_softmax_fill_v1, read_fallback_tau: 1.0, read_fallback_anchor: 0.1}`. Nothing else differs (tested).
- Spec: `plans/261009-0945-m4-sgm-p2p5-occupied-cell-read-fallback-spec/spec.md`.
- Source: branch `m4-sgm-occupied-fill-v1` (this package commit); memsub sha d86639b9… (runner refuses any other local tree). Dev only: no final/intervention/train-split evals, no reserved seeds.

## Pre-registered readout (no thresholds tuned after)
Band = Stage A `classify()` unchanged, on `query_empty_read_weight` = ORIGINAL-stencil absent mass, measured BEFORE fill:

| result | reading |
|---|---|
| band_at_100 = kept (≤ 0.2) | the fill+anchor variant has retained original-stencil support at update 100 (endpoint), this seed. Mechanics only, not retrieval; not attributable to fill or anchor separately. |
| kept_through_100 (all of 0/25/50/75/100 ≤ 0.2) | reported SEPARATELY: an endpoint "kept" can follow an earlier escape and recovery |
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
- **Reservation $1.99 (CONDITIONAL)** = (client 2640 s + 300 s cleanup window) × $0.00067854/s. Assumes (a) the app stops within the 300 s cleanup window after the client exits, and (b) CPU use ≤ 1.25 × 4 cores. Neither is enforced: Modal CPU limits are soft (overuse billed; each extra core over 2940 s ≈ $0.04), and if cleanup cannot verify the stop, billing continues until a manual stop (escalated immediately; not covered by the reservation). **Cap: user 22134 "go" (after the $2.50 ask in 22131 and codex 22133) read as OK of $2.50; these conditional assumptions are restated to the user before launch, which waits for codex v0.2 clearance.** Billing provisional until Modal reports.
- Cleanup (`cleanup-verify`): ONE overall budget of 300 s for the stop call, every app/container list call (each ≤ min(60 s, time left)) and the waits; launch script also kills it at 330 s. Tested with every CLI call hanging.
- Timing: the local client is killed at 2640 s (44 min); server-side deadline killers stop arm work by the 2400 s campaign deadline; app shutdown after that is verified, not enforced.
- A queue delay (Stage A A0 waited 12.7 min) eats campaign time; < 600 s left at entry → refusal, ≈ $0, no retry.
- Local RTX 3060 Laptop (6 GB): not proposed (fit unknown; user's GPU stop).

## Launch procedure (after both approvals)
1. `chat_read` #gravity; confirm worktree HEAD = audited commit, clean tree.
2. From `/home/lenovo/projects/memory-occupied-fill-v1-worktree`: `setsid nohup bash plans/261009-1040-m4-sgm-p2p5-b1-occupied-fill-retention-screen/launch-b1-once.sh > /dev/null 2>&1 < /dev/null &`
3. Watch console/exit; then cleanup-verify verdict, result readout, billing snapshot → #gravity; codex audits.

## Unresolved
- Fill overhead on GPU (gathers every occupied cell per query read; ingestion unchanged).
- λ = 0.1 / τ = 1 untuned; one seed only.
