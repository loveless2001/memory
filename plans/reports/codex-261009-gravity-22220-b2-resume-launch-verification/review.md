# B2 resume deployed and spawned once; first worker claim still pending

User #gravity 22210 authorized this continuation; independent package CLEAR 22219 applies to exact commit `e03ca5a6837db104f79677a492a7d8e889335cdd`. Owner launch receipt records that commit, branch `m4-sgm-occupied-fill-v1`, and PID/PGID/SID 13960, starting at **09:13:26Z**. Independent verification confirms the current HEAD and all eight package file hashes plus memsub match the cleared package.

The one-time launch receipts show **precheck 0 at 09:13:39Z, deploy 0 at 09:13:45Z, spawn 0 at 09:14:04Z**. Deployment logs contain the expected mounted source and `run_b2_remote` function. `run.json` records exactly one acknowledged asynchronous call:

- New app: **`ap-bgncTcGPrYbwfmiQtprLN9`**.
- Call: **`fc-01M4FZ1SZJ6FVRZQ4Y9VCAXMNB`**.
- Write-once resume deadline: **`1791551643.2783465` = 2026-10-09 13:14:03.278Z = 20:14:03 Bangkok**.
- Previous app retained for combined billing: `ap-VsAmnu1E7eS5rXLrKD7vXd`.

The independent read-only Dict/call snapshot completed at **09:14:59Z**. The resume deadline equals the acknowledged dispatch deadline. The original campaign deadline remains `1791546912.6074162` (11:55:12Z); the original start-1 task/claim is unchanged. **Start-2 and start-3 are absent**, and `FunctionCall.get(timeout=0)` indicates the call is still pending. The earlier launch-time app/container listing shows the new app deployed with zero tasks, the old app stopped with zero tasks, and zero containers. These establish deployment and queued/pending dispatch, **not successful GPU checkpoint restoration or training progress**.

The execution package uses a deployed asynchronous call with in-worker absolute deadlines and zero minimum containers. Its computation no longer depends on the local submitting client after the acknowledged spawn. The watcher provides app-stop verification while this PC is available; it is not required for the remote trainer's deadline. The app can remain deployed and idle if the PC is offline when the call finishes; a later `cleanup-verify` receipt is still required before reporting `stopped_verified`. The underlying behavior and assumptions were reviewed in [the package audit](../codex-261009-gravity-22212-b2-resume-v04-review/review.md).

The combined conditional compute reservation remains **$16.04543538 under the same $17 total**, including the preserved $6.07089738 first-segment reserve and $9.974538 continuation reserve. No actual resumed-spend claim is made from this dispatch snapshot. ETA around **19:25 Bangkok** remains the owner's unprofiled projection; queue delay reduces the available four-hour window and can shift or prevent completion. The hard deadline remains **20:14:03 Bangkok**, irrespective of queue delay. No deadline extension, second manual dispatch, extra arm/seed or budget reset is authorized by this verification.

`verification.json`, `run.json`, `apps-live.json`, `containers-live.json` and launch receipts preserve this snapshot. Next checks are an event-driven first-start/continuation audit and a terminal audit: verify start-2, the bound checkpoint-750 continuation/archived partials, then final/partial artifacts, watcher/cleanup exits, stopped/unlisted app plus zero tasks/containers, and combined billing for both app IDs. No training/evaluation forward, deployment, spawn, deadline mutation or start claim was performed by this audit.
