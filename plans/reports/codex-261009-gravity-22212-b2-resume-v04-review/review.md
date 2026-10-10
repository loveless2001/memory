# B2 resume v0.4 r2 at e03ca5a: CLEAR for the already authorized continuation

The exact package at `e03ca5a6837db104f79677a492a7d8e889335cdd` passes independent review. User #gravity 22210 has already authorized Claude to resume this B2 campaign under its existing **$17 total**. This review clears the pending audit gate for **one deploy and one spawn** using this package. Claude remains the launch owner; this audit made no deployment, spawn, remote training/evaluation call, deadline write, or start claim.

The owner worktree was still at this exact commit with a clean tracked tree after verification. An immutable `git archive` snapshot of the relevant package, tests, source, and evidence is retained in `candidate/`; `snapshot.json` records its provenance. Main checkout and protected start-1 evidence remain intact.

## Independent evidence

- **95 focused CPU tests passed in 24.55 seconds**, rerun from the immutable snapshot. They cover resume rules, exact configuration/identity, archive preservation, the unchanged training/evaluator logic, interrupted/uninterrupted tiny CPU parity, cleanup budgets, spawn ordering, and unknown-status behavior. Output: `focused-tests.log`.
- **17 complete worker cases passed with local fakes**, without real trainer processes or Modal calls. They cover successful start-2, rejection of a changed/missing checkpoint, wrong/missing deadlines, foreign campaign marker, exhausted starts, absence of the original start-1, pinned-version mismatch, setup/commit consuming the minimum remaining time, failed initial commit, polling failure, child-watchdog failure, expired entry, and valid start-3. Every spawned fake child is reaped; both watchdog cleanup paths run. Evidence: `independent-worker-checks.py` and `.json`.
- **All eight package file hashes and the memsub source-tree hash match** the manifest. Shell syntax passes. The training script, Stage A dependency and input manifest are byte-identical to cleared `24b1432`. Evidence: `verify-package.py` and `package-verification.json`.
- The protected real checkpoint is still **step 750**, SHA256 `cd1a7e72cbbf4fc2cf92e029395c7e4f78a727d2b6d165b5030bacc1bd753394`. Offline loading confirms its exact PilotConfig and run identity match this unchanged training package and the preserved Volume identity. No model forward, optimizer update, or GPU restore was performed.
- The independent **live read-only precheck returned `ok`**. Thus the Volume checkpoint has the bound SHA, campaign marker matches the original Dict deadline, start-1 is present, start-2/start-3 and the resume deadline key are absent, and the local memsub source matches. `precheck-live.log` retains the result.
- Live app/container listings independently show the original app `ap-VsAmnu1E7eS5rXLrKD7vXd` **stopped, tasks 0**, no resume deployment, and **0 containers**. Raw responses are retained in `apps-live.json` and `containers-live.json`.

## Execution and state boundaries

`modal deploy` plus `Function.from_name(...).spawn(...)` is the documented asynchronous job pattern. A deployed app persists independently of the submitting PC, and functions with no live input default to zero containers. The resume function has no minimum containers or schedule, sets `max_containers=1`, and uses a two-second scaledown window. [Modal apps](https://modal.com/docs/guide/apps), [Modal job queue](https://modal.com/docs/guide/job-queue)

The new deadline is written once under `resume-1-deadline` before dispatch; it is four hours from that write, slightly earlier than the actual spawn acknowledgment. The original campaign deadline and start-1 claim remain untouched. The worker requires the exact new deadline and original campaign marker, rejects a fresh start-1, and admits no more than three total starts. Start-2 additionally requires the exact checkpoint hash; start-3 may use a newer checkpoint and still passes the unchanged training identity/config validation. The trainer archives the prior telemetry before rewriting it from checkpoint rows, preserving the post-checkpoint partial/replayed segment.

The worker arms its process watchdog before blocking setup, rereads remaining time after setup and successful initial Volume commit, and owns/reaps the trainer on every supervisor exit. The child time budget reserves 120 seconds before the deadline; its independent watchdog and the worker watchdog enforce the absolute deadline if a commit/poll blocks. The four-hour function timeout is a fallback. Modal documents that function timeouts are per attempt and exclude scheduling, so the absolute worker deadline is the campaign-level protection. [Modal timeouts](https://modal.com/docs/guide/timeouts)

The local watcher is optional for the computation continuing without the PC. It stops/verifies the deployment on a returned result or deadline plus 120 seconds while the PC is available. Network/status errors never trigger early cancellation. If the PC is offline, idle scale-down is the compute stop assumption; **that is not a stopped-verified receipt**. On return the owner must run cleanup verification and collect the artifacts. A spawn transport failure after the deadline is written cannot authorize a second dispatch: retain the recorded app/deadline state and use bounded cleanup, even if no call ID was received. If deployment fails before an app ID is recorded, inspect/stop any half-deployment by name, as the launcher specifies.

## Combined budget and interpretation

Current public rates match the package: L40S `$0.000542/s`, CPU `$0.0000131/core/s`, memory `$0.00000222/GiB/s`; storage and egress are separate. [Modal pricing](https://modal.com/pricing)

Decimal arithmetic reproduces:

- Conditional rate with the 25% CPU margin: **$0.000678540/s**.
- Resume compute reservation `(14,400 + 300) × rate`: **$9.974538**.
- Preserved first-segment conservative reserve: **$6.07089738**.
- Combined conditional compute reserve: **$16.04543538**, leaving **$0.95456462** within the existing $17 for residual charges, including storage/transfer/backfill. This is not an externally enforced invoice ceiling. CPU overuse, platform/watchdog timing and scale-down remain stated assumptions. The first segment's $5.69262133 provisional bill was not refreshed in this review and is not substituted for its conservative reserve.

The scope remains one seed-0 B2 trajectory to 1,500 total optimizer updates with the original curriculum, dev schedule and paired final bank-derangement evaluation. Start-2 replays **at least 21 already completed updates** from checkpoint 750. GPU continuation is not asserted to be bit-identical. Real deployment/spawn, GPU restore, checkpoint commits during continuation, preemption retry behavior, shutdown and combined final billing still need observation. Installed Modal 1.5.1 source shows `.spawn()` submits asynchronously and `FunctionCall.get()` polls outputs; it does not establish a live preemption recovery test. Preserve the three-start cap and absolute deadline even if platform retries occur; no independent redispatch, extension, extra arm/seed, or budget reset is cleared.

The approximately 3.2-hour ETA still depends on the unprofiled long-input phase. Prior state is **INTERRUPTED_PARTIAL** with no held-out gain and no final memory-use verdict. This clearance concerns execution integrity; the continued experiment must earn its final readout from complete, valid artifacts. A deadline/preemption cutoff remains partial.

## Handoff

Post CLEAR in #gravity. Claude may use user 22210's existing scoped go after the usual immediate channel/source/hash recheck, then launch exactly once. Record the new app ID, call ID, immutable resume deadline and launch exits; retain both app IDs for combined billing. No additional user confirmation is needed for this exact cleared continuation. If a concrete failure changes the package or requires another dispatch, preserve the failure evidence and honor the applicable remaining-start/deadline/approval boundary.
