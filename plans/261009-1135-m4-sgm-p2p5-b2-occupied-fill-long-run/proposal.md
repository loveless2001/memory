# B2 occupied-fill long run — proposal v0.1 (NOT launched)

User 22149 chose option 2 (22147): a proper long run, cap to be quoted before launch. Launch needs codex package clearance + user OK on the cap below + chat_read right before. GPU stop (22058) otherwise stands.

## Question
With `occupied_softmax_fill_v1` (fill + anchor), does the taskhead learn to USE the memory on held-out episodes by 1500 updates, where the identical no-fix recipe did not?

## Arm (one) and its paired reference
- B2 = the readout probe's seed-0 PilotConfig EXACTLY (sha 4e89b95a…: lr 3e-3, batch 16, N32, taskhead, 1500 updates, curriculum filler 0 → 40 at update 1000, dev evals every 100 on heldout seed 4242, 4×16 = 256 queries) + `sgm = FILL` (τ 1.0, λ 0.1). Tested: nothing else differs.
- Paired no-fix reference = probe s0 (same config without `sgm`, same init/stream; A100): dev correct 9 → 5/256 at 1500, pre-fill absent 1.0 from update 300 on.
- Source: branch `m4-sgm-occupied-fill-v1` (this package commit), memsub d86639b9… (runner refuses any other tree). Dev only; reserved seeds untouched.

## Pre-registered readout (no tuning after)
- **memory_used** iff final dev correct(none) ≥ 12/256 (P < 0.001 under Binomial(256, 1/64)) AND paired drop correct(none) − correct(bank_derange) ≥ 6 (same 64 episodes; each episode reads another episode's complete banks).
- memory_used = true → "the fill+anchor variant used memory on held-out episodes, this seed". Not attributable to fill vs anchor; one seed; not a general Qwen claim.
- memory_used = false → "no demonstrated memory use for this variant/seed/recipe". Not "Qwen cannot use memory".
- Reported beside, never criteria: pre-fill absent mass at every eval (band at 1500 with Stage A thresholds; kept-at-every-eval separately), dev correct curve vs probe s0, fill telemetry, read_anchor, task CE (= logged loss − 0.1 × read_anchor).
- Deadline cut before 1500 / INVALID → no readout; evals collected so far are reported as partial; no retry, no extension.

## Stops
One campaign. At most 3 admitted starts (preemption resumes from the last 50-update checkpoint); one immutable deadline across them. No relaunch on the used Dict/Volume, no extension, no second seed, no other arms without a new proposal + codex + user.

## Resources, deadline, cost
- Modal ephemeral `modal run` (not --detach), image im-A7BXMB8v1cVYRvC9pMqZ3i, 1× L40S, 4 CPU, 32 GiB, max_containers 1, Modal retries ≤ 2 (bounded by the 3 Dict start claims), scaledown 2 s; Volume `memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1` (committed every 60 s while training).
- Campaign deadline 23,400 s (6.5 h) after the first call; client killed at 23,640 s; cleanup ≤ 300 s (+30 s kill).
- **Projection (estimate, not a bound):** B1 filler-0 step 8.7 s × 1000 + filler-40 step ≈ 8.7 × 1.53 (probe s0/s1 phase ratio 1.518/1.541) × 500 + 16 dev evals + 1 derange eval + load ≈ 15,900 s ≈ 4.4 h → **expected ≈ $11** at listed base rates. Fill overhead in the longer-input phase is unprofiled (more occupied cells); the 6.5 h deadline leaves ~47% headroom.
- **Reservation $16.24 (CONDITIONAL)** = (23,640 + 300) s × $0.00067854/s; assumes the app stops within the 300 s cleanup window and CPU ≤ 1.25 × 4 cores (both unenforced). Volume storage not priced (one small run directory). **Cap asked: $17.**
- Risks: (1) local client death (WSL/sleep) stops the ephemeral app — committed checkpoints survive on the Volume, but a resume would need a new approval; (2) a slower long-input phase than projected → deadline cut → partial evals only; (3) 3 preemptions → refusal.

## Launch procedure (after both approvals)
1. `chat_read`; worktree HEAD = audited commit; clean tree.
2. From `/home/lenovo/projects/memory-occupied-fill-v1-worktree`: `setsid nohup bash plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run/launch-b2-once.sh > /dev/null 2>&1 < /dev/null &`
3. Progress: Volume telemetry (`modal volume get`, read-only) at most hourly; terminal: both exits, cleanup verdict, readout, provisional billing → #gravity; codex audits.

## Unresolved
- Long-input-phase step time with the fill (unprofiled).
- Worker poll/commit loop exercised by mocked checks only (no GPU run yet).
