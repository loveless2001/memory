# Independent B1 package review v0.1

Reviewed commit **53cd307fa43e9233ae52757adbaf71fc1c42d233** on `m4-sgm-occupied-fill-v1`, using an isolated archive. **HOLD launch clearance pending the corrections below.** The corrected fallback implementation remains cleared; this hold concerns the proposed run package and its claims. User 22128 authorized proposal preparation; no explicit approval of the requested $2.50 launch budget had arrived at the audit's final channel read.

## Verified implementation and controls

All **48 focused CPU checks pass independently**: 7 package, 13 fallback, and 28 Stage A checks. Eight file bindings in the package checksum manifest match exactly. The source hash is `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`, retaining the corrected fallback implementation.

B1 matches A0's bound PilotConfig apart from the three FILL settings, with 100 updates, seed 0, lr 0.003, batch 16 and the same dev schedule/population. Classification uses the original pre-fill absence metric. Accuracy/fill/anchor telemetry are reported beside it. The B1 runner has separate app/Dict identities, one arm, retries zero, one container, the existing image ID and the intended resource/time settings. The Stage A helper is mounted for its import. The launch shell passes `bash -n`.

An independent AST comparison confirms the remote worker's controls match Stage A except for the new child command and temporary-output prefix. Mocked checks directly exercising the B1 worker verify: success, second-start refusal, post-setup deadline refusal, exception guard cancellation, expired-entry refusal, and worker/child guard targets. These checks make no Modal call and launch no real child, sleeper, model or GPU workload. CPU tiny-model fixtures in the focused suite are mechanics checks, not Qwen fit or learning evidence.

## Required correction: shutdown timing and budget representation

The 2640-second outer timeout bounds the local Modal client. It does not guarantee provider-side shutdown or complete cleanup by minute 44. The proposal itself acknowledges unenforced app-stop latency, so channel 22131's hard-stop/worst-case language is stronger than the controls justify.

The current cleanup function permits a 60-second stop CLI call, four rounds of two 60-second list calls, and three 20-second waits: **600 seconds of CLI timeout/wait allowances**, before interpreter/other overhead. The ledger assumes a 300-second stop allowance. An independent fake-clock run through the actual cleanup function and actual verification helper reaches 600 seconds and `shutdown_unresolved`; no real waiting or cloud calls were used. This proves the allowance mismatch, not that a GPU necessarily remains billed throughout verification.

At the package's reserved rate, `(2640 + 300) × 0.00067854 = $1.9949076`. Assuming 600 seconds of billed teardown instead would yield $2.1984696, but neither formula is a guaranteed spend ceiling when provider shutdown latency is unbounded. The CPU +25% factor is also a reserve assumption: [Modal documents soft CPU limits](https://modal.com/docs/guide/resources), with billing based on request or actual use. The listed unit rates match the [current pricing page](https://modal.com/pricing), which also includes load and configured idle time in billing. The resource tuples impose a hard RAM limit but do not turn the CPU margin into a hard dollar bound.

Bound cleanup/stop attempts with a stated overall deadline, align the ledger with that procedure, and revise the user-facing timing and budget to distinguish enforced client/worker bounds from conditional shutdown/resource assumptions. A bounded cleanup timeout must leave shutdown unresolved if it cannot verify zero tasks/containers; it cannot itself establish remote shutdown. Keep no-retry/no-extension behavior. If a strictly guaranteed monetary ceiling is required, this package does not establish one.

## Required correction: endpoint support and causal attribution

The proposal table says a kept endpoint means the anchor kept routing on the memory. This run bundles fill and anchor, so it cannot isolate an anchor effect. Use a statement about the **combined variant's original-stencil support at update 100**, and report `kept_through_100` separately at the registered dev checkpoints.

A direct classifier reproducer with absence values `[0.05, 0.95, 0.95, 0.1, 0.1]` returns endpoint `kept` and `kept_through_100 = false`. Calling that retained support throughout training would miss earlier escape/recovery. The frozen classifier already makes the distinction; no frozen guard or classifier change is needed.

The short gate is designed to assess routing/mechanics. Avoid channel 22131's categorical suggestion that correct answers cannot appear yet. Accuracy may emerge or fail; a useful retrieval claim needs the appropriate held-out and intervention evidence. An empty bank cannot supply a fill, so interpret fully-absent telemetry beside `query_without_occupied_fraction`; supplied fill alone does not establish correct content retrieval.

## Preserved boundaries

No package source was edited during this review. Shared main remains unchanged; all executable checks used the exact archived candidate. The side branch, frozen campaign guards and missing amendment-checkpoint disclosure remain in force. No image build, Modal API/CLI call, GPU access, Qwen forward, paid launch or 100-to-1500 continuation occurred.

After targeted corrections, review the new commit and checks affected by the deadline/ledger changes. A run still needs the user's explicit approval of the corrected, concrete budget and disclosed assumptions. No automatic retry or follow-up experiment is cleared.

Evidence: `snapshot.json`, `verification.json`, `focused-cpu-tests.txt`, `independent-package-check.py` and its JSON output, copied proposal/launch/checksum manifest, and `SHA256SUMS`.
