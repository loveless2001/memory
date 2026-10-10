# B3 — feature_shift=2 on the B2 recipe (proposal v0.2, DRAFT, NOT launched)

Supersedes v0.1 (`proposal.md`, 65eb19b, kept unchanged). Applies codex 22473
(`/home/lenovo/projects/memory/plans/reports/codex-261010-gravity-22465-b3-proposal-review/review.md`, sha 6c237205…).
User 22461 chose option (a). That choice is NOT approval of numerical execution or of the cap. The cap request comes after package clearance.
Authorizes nothing. The sequence is codex proposal clearance → implementation + model-free CPU checks → codex package clearance → the user's cap → `chat_read` → launch.

## Question
Does the shift2 bundle (`feature_shift=2`) let the B2 fill+anchor taskhead meet the exploratory memory-use screen on held-out DEV episodes by 1500 updates, where B2 did not (5/256 normal = 5/256 deranged)?

## Arm (one) and comparator
- **B3 = B2 EXACTLY + `sgm.feature_shift = 2`.** That is the readout-probe seed-0 PilotConfig (manifest sha 4e89b95a…), occupied fill τ 1.0, λ 0.1: lr 3e-3, batch 16, N32, taskhead, 1500 updates, curriculum filler 0 → 40 at update 1000, dev evals every 100, final bank-derange eval.
- **The shift2 bundle (codex 22385/22473):**
  - Every adapter projection (q/k/v/beta) sees [z_t, z_{t−1}], so the input width goes 1024 → 2048, which changes the seeded init draws and scaling.
  - At the **value-token write**, the second block is the preceding key.
  - At a **query**, the second block is the last SOURCE token. That is the last binding's VALUE during training updates 0–999 (filler 0), and the last FILLER token after update 1000 and in all dev evals (filler 40).
  - Every query forks the same post-source snapshot.
- **The offline CPU probe's V+K result** used shift=1 init features, including upstream init-SGM effects. It does NOT certify a live shift2 representation.
- **Comparator = B2** (codex wait42 VALID_NEGATIVE). It is matched on recipe and data, but has different initialization draws/scaling under shift2.
- **Data:** heldout dev seed 4242 is REUSED, already-inspected DEVELOPMENT data, the same population as B2. Reserved/final populations are untouched.
- **Source:** branch `m4-sgm-occupied-fill-v1`. codex reconfirmed that the memsub tree is B2's d86639b9… and the base manifest is 4e89b95a…. B3 needs no memsub edit (`feature_shift` is an existing config field), and the runner binds the unchanged tree.

## Pre-registered readout (identical to B2; thresholds unchanged)
- **memory_used** iff final dev correct(none) ≥ 12/256 AND correct(none) − correct(bank_derange) ≥ 6 on the same 64 episodes. Exploratory operational thresholds; no significance claim.
- **VALID**: the complete B2 validity schema carried over unchanged.
  - Every registered dev eval 0..1500 by 100 occurs exactly once, with integer counts, total 256, episodes 64 and chance 1/64.
  - Accuracy equals correct/total; absence/fill fields are finite and in range.
  - The derange eval is over the same 256.
  - Identity/campaign binding matches.
  - Checkpoints and the trained-parameter file are finite.
- Wording:
  - true → "met the exploratory memory-use screen on heldout dev episodes, this seed (shift2 bundle)";
  - false → "shift2 bundle did not meet the screen for this recipe/seed".
  - Neither is a general Qwen claim. A negative leaves optimization, routing and generalization unresolved (codex 22473).
- Reported beside, never criteria: dev curve vs B2, pre-fill absent mass, fill telemetry, read_anchor, task CE (= loss − 0.1 × anchor), write-gate β by token class.
- Deadline cut / INVALID → no readout; partial evals are reported; no retry, no extension.

## Start, resume and deadline rules (fresh campaign; nothing inherited from B2's resume amendment)
- **≤ 3 TOTAL admitted training starts, including the initial start, so ≤ 2 resumptions.** Starts are claimed atomically in a fresh Dict (`…-b3-shift2-…-starts-v1`).
- **Allowed recovery:** a resumption ONLY after a platform-side interruption (preemption / container loss) of an admitted start. It resumes from the last committed 50-update checkpoint on the fresh B3 Volume.
- **Prohibited:**
  - any retry after a run-side failure (exception, nonfinite, INVALID, refusal);
  - any new launch, new app or redeploy after the campaign starts;
  - any extension;
  - any second seed.
- **One immutable campaign deadline** (fresh: first spawn + 23,400 s), written once and shared by all starts. A start is refused when less than 900 s remains.
- **Bound state per checkpoint:** model/adapter/head params, AdamW moments, global step, torch/CUDA RNG states, data-generator position, and the eval prefix so far. Each start archives its partial suffix (`archive/start-k`); nothing is deleted. Resume equivalence is CPU-tested (crash-after-checkpoint parity, as in B2).
- **Spawned preemption behavior was NOT demonstrated by B2** (start-3 unused). B3 relies on the same untested path, and this is listed as a risk.

## Cleanup and host independence
- **Repair:** every cleanup stop uses `modal app stop --yes <app_id>` (bound id; never name-only). New regression test: a realistic NON-INTERACTIVE CLI fake that behaves like a *deployed* app, aborting without `--yes` (the B2 failure) and succeeding with it. The test asserts the exact argv and the verify-stopped path.
- **Host-independent:** the training run (deploy + one spawn; the in-app deadline/reaper stops the app at the campaign deadline).
- **PC-dependent:** only the local watcher/collector and the manual `collect` / cleanup-verify. If the PC dies, training continues to completion or the deadline. A later `collect` + `cleanup-verify` recovers results and verifies the stop. No relaunch.
- **Test isolation (after M10):**
  - Every CPU negative/gate test has explicit loader/model/cloud sentinels (an env guard + stubs that raise on any model load, `modal` deploy/spawn/stop, or Volume/Dict access).
  - The mutation runner uses its own basetemp.
  - No test can reach Modal or the model.

## Model-free CPU checks (before package clearance; $0)
1. The B3 config resolves with `feature_shift=2`, the adapter input width is 2048, and all else is identical to B2's resolved config.
2. Default-off parity of the B2 path is unchanged.
3. A tiny CPU forward/backward with shift2 + fill (tiny backbone, not Qwen) is finite.
4. Runner deadline, start-guard, resumption-only-after-preemption, refusal, archive and `--yes` cleanup paths pass under fakes.
5. Identity binding refuses B2's Volume/Dict/campaign.
6. Crash-after-checkpoint resume parity holds on CPU.
7. Mutation checks on the guards.

## Cost (itemized; estimate ≠ bound)
- Rates (modal.com/pricing, current base rates): L40S $0.000542/s; CPU $0.0000131/core-s × 4 cores × 1.25 overuse margin; memory $0.00000222/GiB-s × 32 GiB. Total **$0.00067854/s**.
- **Reservation (CONDITIONAL) ≈ $16.08** = (23,400 s deadline + 300 s cleanup) × $0.00067854/s. Its conditions:
  - ≤ 5 billed CPU cores (Modal CPU limits are soft);
  - ≤ 23,700 aggregate billed container-seconds across ALL starts, including startup, refusal and retry tails;
  - memory billed at ≤ 32 GiB;
  - the app stops within the cleanup window;
  - rates unchanged.
- **Other resources:** the image is pinned via `Image.from_id`, so no image build is expected; local file layers mount at deploy. A $0.10 allowance covers any build/registration CPU. Volume storage (a ~35 MB run dir) and the result/telemetry transfer are small and unpriced, stated as an assumption. Late Modal billing is possible.
- **Expected:** B2's **$10.92347 is a reported usage snapshot, not a settled all-resource bill.** No shift2 throughput/memory profile has been reviewed. The width change touches only the small adapter projections (the backbone dominates), so B2-like step times (phase 1 ≈ 10.2–10.8 s, phase 2 ≈ 12.4 s/update on L40S) are a plausible guess, NOT a measured forecast.
- **Explicit proposal:** accept the unprofiled completion risk. A slower run hits the immutable deadline, which bounds cost by the reservation. The result is then partial evals with no readout. No extra paid profile is requested; that would need its own approval.
- **Cap to be asked after package clearance: $17.**

## Stops
One campaign: no second seed, no other arms (z_key-only query and overfit gate are separate future variants, codex 22473), no extension, no relaunch on the used Dict/Volume.

## Unresolved questions
- None blocking. Possible future variants, each needing its own proposal: an asymmetric z_key-only query, and a fixed-set memory-dependent overfit diagnostic.
