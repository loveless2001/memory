# B2 final readout (occupied-fill + anchor, 1500 updates, seed 0)

Written by claude 2026-10-09 ~14:55Z, after the PC reboot. Evidence: `b2-resume-v1/` (collected from the Volume).

## Verdict
- **status valid, memory_used = FALSE.** Final dev with memory: 5/256 correct. With swapped (bank-deranged) memory: 5/256. Chance ≈ 4/256. Gate: ≥12 AND a derange drop of ≥6. Both gates were missed.
- Routing band at the end: **partial**. Empty-read weight .236 at step 1500 (band ≤ .2). It was in band at 300–1200, then drifted up to .22–.24 at 1300–1500.
- Dev correct at 0–1500: 9/8/4/3/3/3/1/3/3/2/2/1/7/5/5/5. The 7 at 1200 is within noise (episode CI ±~4.2).
- Final task loss is near ln64. No sign of learning the task.
- Descriptive lead only, not tested: write gate beta is flat across token classes (key .121, value .121, filler .121, sink .130). At step 1490 the read-output path gets almost no gradient (L6 out_proj ~6e-7, alpha ~2e-6; L13/L20 out_proj/alpha ≤3e-8).

## Execution
- Start-1 (v0.3, ap-VsAmnu…): stopped by the user at ~770; ckpt 750. Start-2 (v0.4 r2, ap-bgncTcGPrYbwfmiQtprLN9, call fc-01M4FZ1SZJ6FVRZQ4Y9VCAXMNB): resume_step 750, returncode 0, wall 8,611 s, volume_commit_errors 0. Start-3 unused.
- The PC rebooted before the call ended (uptime 8 min at 14:47Z). The local watcher (pid 15194) died without writing watch-exit.txt.
- At 14:47Z, read-only: call `done`; app `deployed`, 0 tasks, 0 containers.
- Manual `watch` (`b2-resume-v1.watch-manual.*`) recorded call_result.json. Its cleanup returned **shutdown_unresolved** because `modal app stop` on a DEPLOYED app prompts for confirmation and aborts with no TTY ("Rerun with --yes"). This is a runner bug. The CPU tests never exercised it; the deploy path had never run on Modal. Preserved as `cleanup-attempt1-no-yes-flag.json`.
- Re-ran the runner's own `cleanup_verify` with only `--yes` appended to the stop (`b2-resume-v1.cleanup-manual-yes.log`) → **stopped_verified** 14:52:43Z (state stopped, 0 tasks, 0 containers).
- `collect` → 13 files, gate ok ("B2: valid, memory_used False, band partial").

## Billing (modal billing report, 2026-10-09 UTC)
- start-1 ap-VsAmnu… $5.69262133; resume ap-bgnc… $5.23085059 (hourly 09Z 1.598 / 10Z 2.395 / 11Z 1.238, nothing after 11Z).
- **B2 total $10.92347192 ≤ $17 cap.** Backfill is still possible. B1 ($0.71087545) is a separate approval.

## Hashes (sha256 prefix)
b2_result.json 2a34108de9197116 · final_bank_derange_eval.json f07cded5f68bf0a1 · identity.json 66e36eb0820dca66 · run_manifest.json 7d6e2cb1f2e36695 · trained_parameters.safetensors 2149c97517ad0f84 (8.3 MB, untracked)

## Open
- Fix the `--yes` in the deployed-app cleanup before any reuse of this runner.
- The next step needs a user decision. No compute is authorized.
