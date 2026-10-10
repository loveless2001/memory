# Independent B1 package v0.2 clearance

**CLEARED: 7e9213adc803e06aa43c3c13b56c2190eb32d11d**, parent 53cd307, for the single B1 100-update attempt described in proposal v0.2. Both technical holds in review 22133 are resolved. User 22134's "go" follows the explicit $2.50 request and disclosed limitations; it supplies the scoped launch authorization. Claude restated the conditional assumptions in 22136. No repeat approval is needed for this same attempt; read the channel immediately before launch for any newer stop or scope change.

## Verification

- All **nine affected B1 CPU tests pass**. The 13 fallback and 28 Stage A checks passed in the prior independent review; both test files and their implementations are byte-for-byte unchanged, so those 41 checks were not repeated.
- **Eight additional independent fake-clock cleanup scenarios pass**: hanging CLI calls, slow running-app queries, budget exhaustion between app/container queries, malformed JSON, still-listed containers, lagging task counts, already-stopped apps with a failed stop command, and missing app IDs. All stay within the simulated 300-second budget. Unknown/error states remain unresolved rather than becoming verified stops.
- All eight package file bindings match the v0.2 checksum manifest. The memsub source remains `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`.
- Remote worker and local entrypoint ASTs match the previously reviewed package exactly. Training code/config, the frozen classifier and campaign guards are unchanged. The launch shell passes `bash -n`.
- The owner worktree is clean at the audited commit; shared main remains clean at 95856b153e874508726c604a8c593c6ff73684cb. Checks used an isolated archived source snapshot. No Modal API/CLI operation, GPU use, Qwen forward or launch was performed by this reviewer.

## Holds resolved

Cleanup now uses one monotonic 300-second budget covering stop, each list call and waits. Individual CLI timeouts use the remaining budget, capped at 60 seconds; no CLI call starts with at most one second left. The shared stop-verification logic is reused unchanged. A separate shell timeout kills cleanup at 330 seconds if necessary. The ledger's 300-second allowance now matches the intended cleanup window.

The proposal now attributes endpoint support to the combined fill-plus-anchor variant, reports `kept_through_100` separately at the five registered dev checkpoints, and avoids claiming that retrieval cannot emerge within 100 updates. These remain routing/mechanics outcomes; filled reads alone do not establish correct retrieval.

## Scope and residual assumptions

One arm, seed 0, 100 updates; one launch, no retry or extension, no A2, no reserved populations, and no 100-to-1500 continuation. Use the exact audited worktree/package and record its commit in the launch receipt. Existing per-arm/campaign Dict refusal remains in force. Claude owns launch/collection; this reviewer will not start a competing invocation.

The **$1.9949076 reserve against the requested $2.50 budget is conditional**, assuming provider-side shutdown within the cleanup allowance and CPU usage within the stated margin. Neither the cleanup deadline nor its outer kill guarantees provider shutdown or a strict total-dollar ceiling. Unverified shutdown means the state and any continuing cost are unresolved; it does not prove the app is still running or already stopped. Escalate immediately and stop the bound app if needed, as disclosed. Verify stopped/unlisted with zero tasks and containers before claiming shutdown. Keep billing provisional until backfill is checked.

No Qwen fit or throughput claim is established by CPU checks; the unprofiled variant may fail or time out. A failed/invalid/timed-out attempt must remain recorded, with available artifacts retained and no automatic relaunch. Final collection should report both exits, bound app shutdown, pre-fill absence/classification, fill/anchor telemetry, dev accuracy, and billing scope separately. The missing historical amendment-bound checkpoint remains unavailable; this clearance does not repair or rebind it.

Evidence: `snapshot.json`, `verification.json`, `affected-b1-cpu-tests.txt`, `independent-cleanup-check.py` and its JSON output, exact copied proposal/launch/checksum manifest, `correction.diff`, and `SHA256SUMS`. Prior independent review: `../codex-261009-gravity-22130-b1-package-review/review.md`.
