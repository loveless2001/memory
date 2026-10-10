# B3 proposal v0.3 — two corrections (codex 22475)

Supersedes v0.2 (`proposal-v0.2.md`, 3a8b4df, kept unchanged) only in the two places below. codex 22475 PASSed the v0.2 science and isolated CPU implementation/preparation. Paid clearance and the cap are still pending.

## 1. Deadline termination and app cleanup (replaces v0.2 line 52)
- There is NO remote app-stopping reaper in this design, and none is added.
- **Host-independent:** deploy + one spawn; training runs in the worker. The inherited B2 worker watchdog kills the training child/worker at the immutable campaign deadline (minus the end margin), and the function returns. Once the call returns, no container is running.
- **PC-dependent:** stopping the DEPLOYED app (`modal app stop --yes <bound app id>`) and verifying it (state stopped, 0 tasks, 0 containers) are done by the local watcher/cleanup-verify. "Deployed + zero containers" is NOT `stopped_verified`; only the post-stop verification counts. If the PC is down at the end, the app stays deployed with zero containers until a manual cleanup-verify, and nothing trains or bills compute in between.

## 2. Cost wording and totals (replaces v0.2 lines 78–80)
- The deadline bounds TRAINING TIME. The cost reservation holds only under its listed assumptions:
  - ≤ 5 billed CPU cores;
  - ≤ 23,700 aggregate billed container-seconds across all starts, including tails;
  - ≤ 32 GiB memory;
  - unchanged rates;
  - the cleanup-window stop.
- Reservation with the build allowance: **$16.081398 + $0.10 = $16.181398**, leaving **$0.818602 arithmetic headroom** under the proposed $17 cap. No separate reaper exists, so no reaper cost.
- **Retained Volume state** (measured from the resolved config, adapters built without Qwen):
  - shift2 adapter + head = 3,744,604 params → 15.0 MB fp32 (shift1/B2: 2,155,356 → 8.6 MB, which matches B2's actual 8,625,720-byte `trained_parameters`);
  - a checkpoint with 2 AdamW moments ≈ 45 MB (B2 ≈ 25 MB).
  - Estimate for B3's Volume: live checkpoint + ≤ 2 archived start suffixes (each possibly including a checkpoint copy) + final parameters + telemetry ≈ **≤ ~155 MB**. This is an estimate, to be measured in the CPU dry run. Storage/transfer stay unpriced, as an assumption.
