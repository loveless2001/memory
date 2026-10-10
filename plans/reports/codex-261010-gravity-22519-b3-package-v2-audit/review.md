# B3 package v2 re-audit

Verdict at e551872e971b460b48b8cd60da520aa429daa934: **PASS for both original operational blockers; REVISE the new ledger/procedure window before overall paid-package clearance.** No deployment, spawn or paid step occurred. This is the package re-audit requested by #gravity 22519.

The repaired sources were extracted from the immutable commit to a disposable private tree. That tree's source hashes remained unchanged through the independent checks. Reviewed inputs were retained before removal of the disposable archive; source-manifest.json binds the commit and files. Recreate private-tree from git archive of that commit to rerun check-package.py. The training wrapper and memsub have an empty diff against 52cd79b.

## Original findings closed

1. _volume_files now accepts only Modal NotFoundError or FileNotFoundError as absence. Other listing errors propagate into explicit precheck refusals or failed collection records. The installed SDK's exception module maps gRPC NOT_FOUND to NotFoundError; this establishes the exception class, not a real remote absence observation.
2. Collection requires B3/b3_result.json to have been fetched in the current call. Old local valid result files cannot pass after listing failure or an absent directory.
3. Worker setup and Dict lookup are now within unconditional guard cleanup. Terminal-write errors are returned as diagnostic fields rather than raised through the ordinary function retry mechanism. The admitted-start body remains bounded by the existing start/deadline/terminal guards. Failed watchdog cancellation is returned as an error field; such a field is not proof of successful cancellation.

Independent check-package.py blocked pretrained-model loading, Modal lookup methods and socket connections; hid CUDA and used CPU-only tiny fixtures. Under an actual 2000M/zero-swap cgroup and a 90-second KILL timeout, the registered suite passed **42 tests in 4.07 seconds**, overall driver exit 0. The process read memory.max=2097152000 and memory.swap.max=0.

Independent probes additionally confirmed timeout/permission/service listing refusal; failed/absent-directory collection cannot accept old local results; a current result fetch passes while resume.pt is skipped; entry lookup failure returns refusal with its watchdog canceled; and terminal-write failures on versions, exception and completed paths return diagnostics with canceled guards. No production source or real cloud object was touched.

All **17 retained v4 mutant records** match their exact expected parameter IDs, rc 1 and source mutation patterns. This validates consistency of the retained evidence and source pins. The complete mutant campaign was not independently replayed. The earlier crash-repair, scientific/config/B2 parity and storage-proxy reviews remain applicable within their stated scope.

## Remaining correction: poll lag is not part of the current shared budget

The revised ledger uses 23,400 campaign seconds + 120 seconds watcher grace + 300 cleanup seconds = 23,820 seconds. The watcher checks the backstop once per 60-second poll. After a late poll, it invokes cleanup_verify with its full default 300-second budget; the code does not subtract poll lag or pass an absolute shared deadline.

The independent fake-clock probe starts at 23,519 seconds (one second before backstop), observes a non-completed call, sleeps 60 seconds, and begins cleanup at 23,579 seconds. The permitted cleanup budget then reaches 23,879 seconds, exceeding the ledger's 23,820. This probe measures local control-budget accounting with a fake cleanup callback. It does not measure a real remote stop time, compute usage or a cloud overrun.

The handoff's condition that cleanup must absorb poll lag does not enforce that absorption. Two reviewable options are:

- Reserve the separate default intervals: campaign + grace + one poll + cleanup = **23,880 seconds**. At the already checked 0.00067854 USD/s rate plus the 0.10 USD build allowance, this is **16.3035352 USD**, leaving **0.6964648 USD** under the proposed 17 USD. Preserve status-call/network/stop/service tails as explicit conditions; this arithmetic alone is not an enforced all-resource cap.
- Implement and test an absolute shared watcher/cleanup stop budget, including status-call handling, so the smaller claimed window corresponds to actual code behavior.

Also remove the unconditional statement that post-stop verification bills no containers. A successful stop request/acknowledgement is not independent proof that the app is stopped and all tasks/containers are gone. The package already requires that separate verification; uncertain shutdown tails must remain inside its accounting assumptions. Modal bills application load, processing and idle container time until scale-down to zero. [Modal pricing](https://modal.com/pricing)

These narrow ledger/procedure changes were sent to Claude in message 22521. They do not authorize a higher cap, added compute, reaper, profile, manual retry or scope expansion.

## Boundaries

The procedure now correctly calls precheck resource preparation/checking and distinguishes admitted training starts from deployed-container crash reschedules. MAX_STARTS does not bound every container attempt; the PC-dependent stop and crash-loop risks remain explicit. [Modal retries guide](https://modal.com/docs/guide/retries), [Modal scaling settings](https://modal.com/docs/guide/scale)

The approximately 197 MB payload-based peak / 200 MB storage allowance remains an estimate with CPU RNG, identity, telemetry and other-file caveats. Storage/transfer and settled billing remain conditional. Current rates were verified in the preceding audit; this re-audit did not query account allowances or billed usage.

Next trigger: committed ledger/procedure correction with source/test/handoff hashes. The original operational blockers are closed. Overall paid-package clearance and the user's numerical/cap decision remain pending. No Qwen weights, GPU, cloud lookup, deployment, spawn or paid operation occurred here.
