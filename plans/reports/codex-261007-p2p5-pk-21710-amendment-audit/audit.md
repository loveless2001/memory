# Independent audit: user21710 option B, frozen a17cd40

PASS for the exact approved post-hoc validation amendment and one readings run under the existing reserve and controller horizon. No implementation blocker found. This is engineering clearance; readings have not started and no new scientific result is established.

Reviewed commit: `a17cd401c9046b1aa92826c0ecb47914d06270c7`.
Package index: `efc80e8b473cf76900b4bc1a5259abdb65cba6b5d66f0d9baae9e62bd001a8a3` (all 17 indexed files match).
Analysis/launch manifest: `882dd4a443307fa4e248b8393e5ec884a714dc215f2967e30b2facbc6d520492`.
Numerical memsub tree remains `2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b`.

The full exception spec matches the independent pre-amendment baseline: one cell, learned-n32-s1; epoch/attempt; original FAILED state and exact reason; state/done/seven output hashes; terminal generation/checkpoint; and exactly 51 grad_norm leaves at 17 steps. The original validator must reproduce the original failure; its remaining stages and the amended structural-schema check still apply. update_norm receives no exception. Other FAILED/LOST cells continue to block.

The real fetched campaign binds 17 cells under the original gate, with `learned-n32-s1: state FAILED`, and all 18 under the amended gate. All 18 state files and terminal checkpoint payloads match the previous independent terminal audit. The FAILED evidence is retained. The write-once revalidation CLI independently reproduced the submitted record byte for byte (`e4a2a04e…`); a second invocation refused and preserved those bytes.

Independent verification:

- Focused campaign and amendment tests: **68 passed, 2 skipped**, exit 0 (`focused-tests.log`). The real-evidence amendment tests ran; the two existing skips are tiny end-to-end tests.
- Private-copy mutation rerun: baseline **27 passed**; **all 15 mutations caught by their intended tests**, with each copy's manifest re-frozen (`mutations-independent.json`). No shared source mutation was used.
- Eighteen local audit checks passed (`local-audit.json`), including a fresh exact dependency-manifest reconstruction, the exact four-analysis/three-launch manifest delta, unchanged scientific inputs, real gates, record reproduction, and additional early-identity/parity/end-binding failure probes. Whole-campaign and both-N labels persist; end-binding failure retains the original unavailable reading (`label-probes.json`).
- Read-only Modal refresh completed **2026-10-07 15:31:40 UTC** (`remote-audit.json`): all nine training apps stopped/unlisted with zero tasks/containers; original guards and registry unchanged; readings app deployed idle, with no guard/admission, local launch directory, or running container. Controller remains deployed with its original bindings.

The owner may re-read #gravity, redeploy the inert readings app from this frozen package, spawn once, then collect and independently verify shutdown. Existing runtime identity checks must see the amended manifest. The latest candidate remains **2026-10-07 17:06:30.652974 UTC** (**00:06:30.652974 on Oct 8, Bangkok**); the controller deadline remains **21:26:57.252974 UTC**. The existing reserve and one-admission/retries-zero restrictions continue to apply. Retraining, reseeding, rescue, another readings attempt, or a controller extension are outside this clearance.

Both N results must retain **post-hoc amended** labels and the original protocol outcome **unavailable**. The cause and scientific impact of the missing gradient diagnostics remain undetermined. Billing reconciliation was not performed here; the conditional reserve is not a platform-enforced cash ceiling.

Reviewer actions: local CPU checks, private copies and read-only remote queries only; no shared campaign artifact edits, deployment, invocation, stop, commit or push.
