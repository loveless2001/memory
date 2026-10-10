# B3 — feature_shift=2 on the B2 recipe (proposal v0.1, DRAFT, NOT launched)

Origin: user 22461 chose (a), a small capped shift=2 training screen, after the CPU information probe (CARRIED; appending the key-token state recovers the key at ≥ .91; codex PASS 22457/22459).
Authorizes nothing. Needs codex proposal review → implementation + CPU checks → codex package clearance → the user's cap → `chat_read` → launch.
Exploratory, single seed. Earlier negatives stay closed.

## Question
Does giving the write projections the previous token's state (`feature_shift=2`, so the value-token write sees [z_value, z_key]) let the taskhead learn to USE the memory on held-out episodes by 1500 updates, where B2 did not (5/256 normal = 5/256 deranged)?

The probe showed the preceding key is only partly recoverable from z_value (24–66% top-1) but near-perfectly from [z_value, z_key] (≥ .91). Whether training exploits that is the open question.

## Arm (one) and its paired reference
- **B3 = B2 EXACTLY + `sgm.feature_shift = 2`.** That is the readout-probe seed-0 PilotConfig (manifest sha 4e89b95a…) + `occupied_softmax_fill_v1` (τ 1.0, λ 0.1): lr 3e-3, batch 16, N32, taskhead, 1500 updates, curriculum filler 0 → 40 at update 1000, dev evals every 100 on heldout seed 4242 (4×16 = 256 queries), plus the final bank-derange eval.
- **What differs, and only this:** `feature_shift` 1 → 2. This necessarily changes the q/k/v/beta input width (1024 → 2048) and therefore their seeded init draws, and it gives the query step [z_key, z_previous] where the previous token is usually filler (codex 22385 §2). This is the shift2 bundle, not a pure information manipulation.
- **Paired reference = B2** (codex wait42 VALID_NEGATIVE): final 5/256 normal vs 5/256 deranged, dev curve 9/8/4/3/3/3/1/3/3/2/2/1/7/5/5/5. Same dev population and derange construction.
- **Source:** branch `m4-sgm-occupied-fill-v1` at the package commit. The memsub tree is bound and must be unchanged from B2's d86639b9… if no memsub edit is needed; that is to be confirmed in implementation, and `feature_shift` is a config field.

## Pre-registered readout (identical to B2; no tuning after)
- **memory_used** iff final dev correct(none) ≥ 12/256 AND correct(none) − correct(bank_derange) ≥ 6 on the same 64 episodes. These are EXPLORATORY operational thresholds, with no significance claim (4 queries share each episode).
- **VALID** only if every registered dev eval (0..1500 by 100) occurs exactly once with integer counts over 256, a finite pre-fill weight in [0, 1], and a derange eval over the same 256.
- memory_used = true → "with the shift2 bundle, the fill+anchor taskhead used memory on held-out episodes, this seed". This is not attributable to information alone (bundle), and is not a general Qwen claim.
- memory_used = false → "shift2 bundle did not rescue this recipe/seed". This is not "Qwen cannot use memory".
- Reported beside, never criteria:
  - dev curve vs B2;
  - pre-fill absent mass;
  - fill telemetry;
  - read_anchor;
  - task CE (= loss − 0.1 × anchor);
  - write-gate β by token class.
  - Optional $0 follow-up on the final weights, only if the user asks: the existing CPU geometry diagnosis (q·k bound rank, k/v collapse).
- Deadline cut / INVALID → no readout; partial evals are reported; no retry, no extension.

## Execution design
- **Runner:** derived from the audited B2 resume runner pattern: `modal deploy` + ONE `spawn` (host-independent), an immutable campaign deadline, ≤ 3 admitted starts with 50-update checkpoint resume, and a fresh app/Dict/Volume (`…-b3-shift2-…`).
- **Prerequisite carried from the B2 audit (codex 22287/22290):** the cleanup stop uses `modal app stop --yes`, with a realistic deployed-app CLI cleanup regression test, new hashes and codex review.
- **Resources:** 1× L40S, 4 CPU, 32 GiB, `max_containers=1`; checkpoints every 50 updates on the Volume, committed every 60 s.
- **Model-free CPU checks before any paid step:**
  - B3 config resolves with `feature_shift=2` and the input width is 2048;
  - default-off parity of the B2 path is unchanged;
  - a tiny CPU forward/backward with shift2 + fill runs and is finite;
  - the runner's deadline, start-guard and cleanup paths pass under fakes;
  - the identity binding refuses a B2 Volume/Dict.

## Cost (estimate, not a bound)
- B2 actual: $10.92 for 1500 updates (start-1 $5.69 + resume $5.23, including ≥ 21 replayed updates). Measured: phase 1 ≈ 10.2–10.8 s/update, phase 2 ≈ 12.4 s/update on L40S. The shift2 width change touches only the small adapter projections (backbone-dominated), so **expected ≈ $11–12**.
- **Reservation (CONDITIONAL):** a campaign deadline of 23,400 s (6.5 h), plus 300 s cleanup, × $0.00067854/s ≈ **$16.08**. It assumes the app stops within the cleanup window. **Cap to be asked: $17**, the same as B2.
- **Risks:**
  - a slower phase 2 → deadline cut → partial evals only;
  - 3 preemptions → refusal;
  - Modal late billing.

## Stops
One campaign. No second seed, no other arms, no extension and no relaunch on the used Dict/Volume without a new proposal + codex + user.

## Unresolved questions (for codex)
- Should a small fixed-set, memory-dependent overfit gate (codex 22385 §5; ≲ $2) run first, so that a pure inability to learn is caught before the $12 screen? Default: no. The user chose the screen, and B2-style dev evals every 100 updates already show early trends.
- Should the query-side `[z_key, z_previous]` be kept as-is (shift2 bundle, matches the toy), or should the query use z_key only (a role-separated variant)? Default: keep the bundle (one change vs B2).
