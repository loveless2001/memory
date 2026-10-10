# B3 package audit at 52cd79b

Verdict: **REVISE before paid package clearance.** The scientific recipe, earlier crash repair and CPU test evidence pass their reviewed scope. Two independently reproduced operational gaps violate the package's freshness and no-run-side-retry contracts. The user's numerical/cap decision should follow the repaired package audit, not precede it.

Scope: #gravity handoff 22513; commit 52cd79b0d45f48504db4c8c6d6a167a017d74051. The sources were extracted from that immutable commit to a disposable private tree. No shared production source was edited. The private tree was removed after preserving 96 relevant inputs and the source manifest; synthetic CPU test artifacts, check script and output remain here. Recreate private-tree from git archive of the recorded commit to rerun check-package.py.

At close-out the shared runner and test file had concurrent uncommitted changes, after findings 22515/22516 were sent. Those evolving changes are not part of this verdict. The captured 52cd79b inputs and their hashes remain unchanged; a new committed handoff is required for their replacement audit.

## Required fixes

### 1. Volume failures must not establish freshness or collection success

Runner lines 299-313: _volume_files catches every Exception and returns an empty list. Independent fake Volume TimeoutError and PermissionError both made precheck return None, meaning success/freshness. The caller therefore proceeds without establishing whether the bound run directory is empty.

The same helper is used by collect at lines 385-400. With a prior local valid result and recorded successful call, an injected Volume-listing timeout returned files=0 and ok=True. This accepts an existing local result as though the requested collection succeeded.

Accept an absent run directory only through a specifically established absence condition. Treat transport, authentication/permission, service and parsing errors as failure/refusal. Collection must not gate stale local artifacts after listing failure. Add CPU negative cases for both precheck and collect, including pre-existing local output. Do not infer absence from a generic exception.

The installed Modal Volume.listdir implementation delegates to iterdir and its RPC; the read_file method's FileNotFoundError conversion does not establish that listdir uses that same conversion. Verify the actual list-path absence contract in the local SDK or explicit API evidence when choosing the narrow exception condition.

### 2. Setup and terminal-write errors must remain inside controlled failure/cleanup

Runner lines 212-214: the worker watchdog is created before the Dict lookup, but the lookup occurs outside try/finally. An independent injected lookup failure escaped with one watchdog created and zero canceled. A real sleeper remains armed against the worker process and the exception is eligible for ordinary function retries.

Runner lines 245 and 248-252: if a terminal Dict write fails, the exception handler calls mark_terminal again; a second write failure escapes. The independent probe completed a fake child successfully, injected terminal-write failure, and observed the exception propagate despite watchdog cancellation. Since the function has retries configured, this undermines the promise that a run-side failure/refusal cannot cause another ordinary function attempt.

Enclose all setup that follows guard creation inside unconditional guard cleanup. Contain lookup and terminal-write errors as explicit refusal/diagnostic outcomes even when a durable terminal marker cannot be written; do not turn those operational failures into ordinary function retries. Retain the platform-interruption recovery contract separately. Add tests that establish no leaked guard, no child launch when setup fails, and no retryable exception when terminal recording fails.

These findings were sent to Claude in message 22515. They require a source/test fix and re-audit; no source fix was made by this auditor.

## Package-note corrections

The note's precheck is not strictly read-only: the Dict lookup and configured Volume use create_if_missing=True, so preparation can create named resources. Describe that action accurately in the post-approval procedure.

The <=3 starts guard limits admitted training starts. It does not bound every container startup, failed startup, refusal or retry tail. Modal documents that deployed-app container crashes can be rescheduled indefinitely, separately from configured function retries. The claimed PC-down idle/zero-container condition applies to the healthy completed path and must not be generalized to crash loops. This is an external-documentation inference about this runner's exposure, not an observed B3 cloud run. [Modal failures and retries](https://modal.com/docs/guide/retries)

Keep that distinction explicit in the procedure/ledger and fail-stop on unknown service state at the launch gates. No added paid profile, reaper, manual retry, redeploy or higher cap is implied by this audit. These documentation points were sent in message 22516.

## Verified scope that passes

- B3's wrapper differs from B2 through the campaign/result/identity naming and feature_shift=2 bundle, with the registered training, evaluation, summary and checkpoint/archive behavior otherwise retained. The registered base manifest and memsub hash match in the private copy. The shift2 bundle, changed initialization/widths, source-token query context, reused seed-4242 dev data, 12/256 correct plus paired >=6 drop screen and exploratory wording are appropriately disclosed. This remains one-seed development evidence, not a general memory-use conclusion.
- The registered 32-test package suite independently passed in 4.37 seconds. The overall driver exited 0. It ran once under a 2000M memory/zero-swap cgroup with a 90-second KILL timeout, one CPU thread setting, CUDA hidden, pretrained-model loaders blocked, Modal lookup methods blocked and socket connections blocked. Actual cgroup limits were read by the process (memory.max=2097152000, memory.swap.max=0). Tiny-backbone numerical fixtures were executed; no Qwen weights or GPU work were loaded.
- The source and output are retained in check-package.py, independent.log and independent-results.json. The five fault observations are separate from the passing registered suite; a passing suite does not clear those uncovered paths.
- Harness v3 uses exact parameter IDs and writes child output to files, reading only the last 256 KiB. Pure independent classification checks rejected a wrong parameter ID and infrastructure failure while accepting the exact expected ID. All 11 retained v3 records match their exact source pins and reported rc-1 failure IDs. The systemd journal corroborates the parent scope and baseline/M1-M11 child launches. The full mutant campaign was not independently replayed, and the journal alone does not prove the historical parent's 512M property; its capped invocation remains reported evidence.
- The earlier v2 JSON remains unchanged and v1 evidence is marked superseded. The disposal approach retains the earlier shared-source crash-safety repair.
- The approximately 197 MB payload-based peak / 200 MB estimate explicitly supersedes 155 MB in the package note. The CPU-state/telemetry/identity/CUDA-RNG and other-file limitations remain visible. This is accepted planning evidence, not a measured real GPU Volume bound.

## Ledger review

Current official base prices match the package constants: L40S 0.000542 USD/s, CPU 0.0000131 USD/core/s and memory 0.00000222 USD/GiB/s. The proposed five-billed-core margin and 32 GiB yield 0.00067854 USD/s; 23,700 aggregate seconds plus the 0.10 USD build allowance yield 16.181398 USD, leaving 0.818602 USD below the proposed 17 USD. These are conditional arithmetic, not an enforced cap or settled bill. [Modal pricing](https://modal.com/pricing)

The same pricing page lists Volume storage at 0.09 USD/GiB/month and egress at 0.04 USD/GiB before included allowances. Thus rates are published, while the package's storage retention/export quantity and remaining account allowances are unbound. For scale only, 200,000,000 bytes at those rates would be approximately 0.016764 USD per retained month and 0.007451 USD per full export before allowances; this does not establish the campaign's all-resource total. Carry a stated retention/export basis or explicitly retain that budget assumption. No account balance, billed usage or cloud resource state was queried. [Modal pricing](https://modal.com/pricing)

The deadline limits worker/training lifetime under its implementation and does not prove <=23,700 aggregate billed container-seconds, crash-loop cessation, maximum CPU usage, timely PC-dependent cleanup or an all-resource 17 USD ceiling. A build allowance is also an allowance rather than a measured bill. The unprofiled throughput/completion risk remains explicit; no extra profile is authorized.

## Handoff boundary

Repair the two operational paths, update the noted procedure/risk wording, retain prior evidence, and provide new source/test/ledger hashes for re-audit. Paid package clearance and the numerical/cap decision remain pending. No deployment, spawn, real checkpoint restore, Qwen/model load, GPU, account lookup or paid operation occurred here. Public documentation was read solely to verify semantics and current rates.
