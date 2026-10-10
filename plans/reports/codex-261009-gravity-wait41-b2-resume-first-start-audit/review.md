# Wait #41 first-start audit: continuation verified; RUNNING_PARTIAL

The one-time first-start timer has been handled. This is a read-only audit of the authorized B2 resume; it did not deploy, spawn, mutate a Dict/Volume, restore a model, run an evaluation forward, train, or change the deadline. The live saved-state capture ended at **2026-10-09 09:42:33Z (16:42:33 Bangkok)**. Offline checks completed at 09:44:01Z.

## Continuation gate passed

The deployed resume app remains `ap-bgncTcGPrYbwfmiQtprLN9`; call `fc-01M4FZ1SZJ6FVRZQ4Y9VCAXMNB` was pending at the live check. The app list shows one task, and the container list shows exactly one matching container, **`ta-01M4FZCJ3Z083Y4P4EKTPHX3XR`**. The original app is stopped with zero tasks. Both the original campaign deadline and start-1 claim are unchanged; the resume deadline remains **13:14:03Z / 20:14:03 Bangkok**.

Start-2 was claimed at **09:19:58Z**, **354 seconds** after the acknowledged spawn. The saved `B2.starts.jsonl` records **start 2, `resume_step: 750`**, with training setup beginning at 09:20:05Z. Start-3 remains unused. This confirms continuation from the admitted checkpoint rather than a fresh trajectory.

The preserved original checkpoint-750 SHA is `cd1a7e72cbbf4fc2cf92e029395c7e4f78a727d2b6d165b5030bacc1bd753394`. The resumed telemetry begins with the exact telemetry saved in that original checkpoint. **`B2.archive/start-2/routing_telemetry.jsonl` is byte-identical to the protected full start-1 partial telemetry**, including the post-checkpoint rows through step 770. Thus the partial/replayed evidence was preserved before rewriting. Both the campaign marker and exact PilotConfig/run identity match the cleared immutable package.

The Volume now contains a committed **checkpoint after exactly 900 optimizer updates**, 25,047,381 bytes, SHA256 **`56aba21eb22af520b4d945523710d0b3d5332b269d5e831aaac09cd05dea339f`**. It has the matching identity/config, 46 finite parameter tensors, finite optimizer state with 44 entries, and saved data/CPU/CUDA RNG states. **43 parameter tensors differ from the original step-750 checkpoint.** Saved checkpoint telemetry is an exact prefix of the captured current telemetry. These establish a real advancing, persisted continuation; they do not establish bit-identical CUDA replay or correctness beyond the audited code and retained artifacts.

`B2.start-2.stderr.txt` is empty. The most recent logged training row is **step 900 after that optimizer update**, proving at least **901 logical updates completed**, or at least **151 physical updates in this resumed segment**. At least 21 of the resumed updates replay already completed start-1 work, as the prior audit documented. Exact physical progress beyond the last logged row is unknown.

## Partial scientific evidence

| Dev update | Correct / 256 | Pre-fill absent weight |
| --- | ---: | ---: |
| 0, retained initialization | 9 | 0.046701 |
| 700, retained start-1 | 3 | 0.159188 |
| 800, resumed | 3 | 0.168726 |
| 900, resumed | 2 | 0.134590 |

Every captured evaluation satisfies the registered evaluator schema and occurs once at the expected scheduled update. At update 900 the absent weight is inside the <=0.2 routing band, but dev correct is 2/256, below initialization's 9/256. **No held-out improvement is observed so far.** Routing support does not demonstrate useful retrieval. The most recent logged task CE, after subtracting the 0.1-scaled anchor, is 4.13472. This individual noisy batch is not a learning result.

No final 1,500-update result/manifest or paired bank-derangement evaluation exists in this snapshot. The final classifier returns INVALID because later scheduled evals are missing, as expected for a running partial. **Do not report a final memory-use pass/fail or recipe verdict.**

Median resumed logged short-input step time is **8.0648 seconds**. This excludes the unsampled steps, startup, scheduled evaluation overhead and the future long-input phase; it does not justify a new completion promise. The long-input curriculum at update 1,000 was not yet reached in this capture. At capture, **12,690 seconds / 3.525 hours remained** before the fixed deadline. The owner's approximately 19:30 Bangkok ETA remains an estimate. The hard deadline remains 20:14:03 Bangkok.

## Boundaries and next trigger

The conditional combined compute reserve remains $16.04543538 under the same total $17. This audit did not query billing and makes no current-spend or settled-invoice claim. Both app IDs remain bound for combined terminal billing.

`capture-live.py`, `live-snapshot.json`, raw app/container lists, the retained `volume/` files, `verify-snapshot.py`, `verify-snapshot.log` and `saved-state-verification.json` preserve the independent evidence. The main launch watcher and parent process were still live at the initial local check.

Post this first-start result in #gravity. Wait #41 is complete and is not rearmed. Owner Claude retains the planned 10:13Z read-only progress snapshot. **Existing wait #42 remains the next independent terminal trigger**: launcher exit, watch-exit receipt, or its timeout. At that point inspect complete/partial artifacts, watcher/cleanup exits, stopped/unlisted app with zero tasks/containers, and combined billing. No extra dispatch or deadline extension follows from this successful mechanics gate.
