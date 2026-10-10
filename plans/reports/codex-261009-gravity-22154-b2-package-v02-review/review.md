# B2 v0.2 @ ed82721: HOLD for remaining lifecycle and validation fixes

Candidate `ed82721242a3384000227959e08c5bbf5394e29d` was independently exported into an isolated snapshot. The main checkout remains `95856b1`; candidate memsub remains `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`. No GPU, live Modal methods, new remote resource, launch, merge, or existing experiment-artifact mutation occurred. The requested $17 approval remains pending. Findings posted in #gravity 22155, replying to 22154.

## Original fixes verified

All eight package file bindings and the source tree binding match. Shell syntax passes. **46 focused CPU tests pass in 15.81 seconds** (B2, B1, fallback). The committed owner receipt reports 78; this audit independently ran the 46 directly affected tests.

Fourteen full-worker mock cases replace remote Dict/Volume, processes, guards, kills, and clock. The new supervisor's clock and kill defaults are explicitly injected so the test never calls the real OS kill path. Evidence lives in `independent-worker-checks.py` and `.json`.

The original child-watchdog creation failure now kills and reaps the trainer. Original duplicate-evaluation, wrong-count/total, negative-derange, and NaN absent-weight cases all return INVALID. Unidentified/foreign same-config checkpoints refuse. Temporary-directory checks confirm both pre-checkpoint partial artifacts and post-checkpoint telemetry survive in archives. The tiny uninterrupted/resumed parameter and telemetry comparison still passes. Start-1 also refuses a populated Volume run directory. The significance claim was replaced with exploratory operational thresholds.

## Remaining concrete failures

1. **Process-exit race skips guard cleanup.** After a polling exception, let `child.poll()` report live and `killpg()` raise ProcessLookupError because the group exits between those operations. `supervise_child` exits before `child.wait()` and `cancel_killer(guard)`. The outer worker cancels its guard, leaving the child guard uncancelled and replacing the original error. Put child-guard cancellation in an unconditional nested finally, tolerate the normal ProcessLookupError race, and reap the child. Apply the same race handling to `cancel_killer` itself.

2. **Minimum startup time is checked before the new blocking commit.** With 2,000 seconds initially remaining, let the initial commit take 1,900 seconds. Remaining time is 100 seconds, below MIN_START_S=900 and END_MARGIN_S=120, but the worker still spawns the trainer with `child_s=-20` and immediately times it out. Revalidate MIN_START_S after the initial commit, immediately before trainer creation. The mock stays before the absolute campaign deadline, so this reproduction does not depend on pretending that a real deadline watchdog failed.

3. **Initial commit failures are omitted from the record.** When only the initial commit fails, the worker's `volume_commit_errors` is zero. Count this failure in the returned record, or refuse before training if the campaign marker cannot be persisted. This matters when describing restart durability.

4. **Result schema validation is incomplete.** The five original counterexamples are fixed. Additional inputs still yield valid / memory_used=true: final accuracy contradicting its correct count; episodes=1 with total=256; NaN fill support; and NaN deranged absent weight. Validate the actual evaluator schema, including the registered 64 episodes, count/accuracy consistency, finite/ranged routing and fill metrics for both conditions. These fields are emitted by the actual evaluator; the tests currently substitute a smaller schema that omits them.

## Bounds and interpretation retained

The compute reservation remains `$16.2442476`, conditional on its disclosed CPU and shutdown assumptions. Storage and egress remain outside that ledger, and longer-input fill timing is unprofiled. The estimated $11 / 4.4 hours is not a bound. A three-start ledger bounds admitted starts rather than all possible container births. Checkpoint writing and successful persistence remain separate facts. Full discussion and primary [Modal pricing](https://modal.com/pricing), [Volume](https://modal.com/docs/guide/volumes), [retry](https://modal.com/docs/guide/retries), and [preemption](https://modal.com/docs/guide/preemption) references are retained in the v0.1 audit.

Keep 12/256 correct and a six-correct paired derangement drop as operational criteria for this exploratory recipe and seed. Report their observations and limitations; matching a historical A100 recipe does not establish bitwise equality on L40S. B1's train/dev length mismatch also does not prove learning was impossible within 100 updates.

## Stop point

HOLD remains until the reproduced failures are corrected and the exact amended package is audited. No paid launch is cleared here. Existing B1 billing wait #37 remains scheduled for after 05:05Z; it was not polled early. The v0.1 audit, reproductions, and candidate files remain in their separate report directory.
