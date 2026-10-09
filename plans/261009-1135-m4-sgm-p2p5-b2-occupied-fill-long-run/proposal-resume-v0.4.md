# B2 resume v0.4: continue start-1 from update 750 (NOT launched)

User 22196: "stop it and resume later". Start-1 (v0.3, app ap-VsAmnu1E7eS5rXLrKD7vXd) was stopped by a manual SIGTERM at 07:54:07Z. Cleanup verified it stopped (0 tasks, 0 containers). It reached update ~770; the Volume checkpoint is at update 750 (`resume.pt` sha cd1a7e72…, 23.9 MiB). The v0.3 package cannot resume after 11:55:12Z, because its deadline is immutable. v0.4 adds only what a later resume needs. Launch needs codex clearance, a user go, and a chat_read right before.

## What stays identical
- Train script, memsub (d86639b9), probe-s0 config + FILL, Dict `m4-sgm-p2p5-b2-occupied-fill-long-starts-v1`, Volume `memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1`, run dir `/vol/b2-run-v1`, image, L40S/4 CPU/32 GiB, ≤3 starts in total, the pre-registered readout (unchanged, see proposal.md).
- The worker helpers (guards, supervise_child, claims, campaign binding, cleanup) are byte-identical to v0.3; a test compares their source.
- Evidence (`b2-resume-v04-checkpoint-acceptance.txt`): the real checkpoint's identity, the Volume identity.json and the locally computed run identity are equal, so the unchanged train script accepts the run dir at start-2. Its telemetry ends at eval 700 / train row 740. Rows 750–770 from start-1 get archived by the train script (B2.archive/start-2), not deleted.

## What changes (runner `modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py`)
1. **Runs without this PC.** `modal deploy` (app `memsub-m4-sgm-p2p5-b2-occupied-fill-resume1`) plus ONE `.spawn()`. GPU time is bounded inside the worker:
   - the child is killed at deadline − 120 s;
   - the worker is SIGKILLed at the deadline;
   - a start after the deadline refuses at entry;
   - the function timeout (4 h) is the backstop.
2. **Fresh deadline:** 14,400 s (4 h) after the spawn, written once under `resume-1-deadline` in the same Dict. The original deadline stays the campaign identity, checked against campaign.json.
3. **Resume only:**
   - a claimed start-1 refuses, and so does a missing `resume.pt`;
   - the local precheck (read-only; passed live: `b2-resume-v04-precheck-live.txt`) requires start-1 claimed, start-2/3 and the resume key absent, and campaign.json equal to the Dict's campaign.
4. **Order:** `precheck → deploy → spawn-resume` (records the app id, then the deadline, then the call id) `→ watch`.
   - `watch` stops and verifies the deployed app when the call returns, or at deadline + 120 s. It only works while this PC is up. A failed status read never stops the run early.
   - If the PC is off, the deployed app sits idle with no containers once the call ends, and I run cleanup-verify on return.
   - `collect` fetches the run dir without resume.pt.

## Time and cost
- **Projection (estimate, not a bound):** ≈ 11,450 s ≈ 3.2 h.
  - Startup ~400 s, from start-1's launch-to-train time.
  - 250 short-input updates × 10.8 s (start-1, all-in).
  - 500 long-input updates × ~16.5 s. This phase is unprofiled; it assumes the probe's 1.53× ratio.
  - Plus the final derange eval.
- **Deadline risk:** the 4 h deadline holds a long-input slowdown up to ~2.0×; beyond that the deadline cuts the run, giving partial evals and no readout.
- **Expected cost** ≈ $7.7 (start-1's full 06:00Z hour billed $2.40).
- **Reservation:** (14,400 + 300) s × $0.00067854/s = **$9.97** (conditional, ledger()).
- **Start-1 provisional:** $5.69 (billing rows 05–07Z).
- **Campaign bound $15.67 ≤ the approved $17 cap.** No new cap asked.

## Risks / unverified
- A deploy + spawn call has not been exercised on Modal yet; only CPU tests with fakes cover it.
- Modal 1.5.1 drives `.remote()` retries from the client (v0.3 relied on that). Whether a spawned call is retried after a preemption is unverified. A preemption may simply end the call at its last checkpoint; any further start needs a new OK.
- GPU continuation from a checkpoint is not bit-identical to an uninterrupted run (GPU nondeterminism). The CPU resume parity test is exact.
- Readout caveat added: one interruption plus a resume at update 750.

## Checks
- 95 focused CPU tests pass (`focused-tests-v0.4.txt`), including 15 new resume tests.
- Live read-only precheck: ok.
