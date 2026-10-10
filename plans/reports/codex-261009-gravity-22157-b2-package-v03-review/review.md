# B2 v0.3 @ 24b1432: CPU package CLEAR, paid approval pending

Independently audited `24b1432e990f878d1d8dfc9fa9183357fa9986bc`, branch `m4-sgm-occupied-fill-v1`. All reproduced v0.1/v0.2 blockers are resolved in this exact package. This clears the CPU preparation/package gate for the proposed single B2 campaign. It does not launch the campaign or supply the user's pending $17 approval. Main checkout remains `95856b153e874508726c604a8c593c6ff73684cb`; tracked working trees are clean.

## Independent evidence

- **52 affected CPU tests pass in 15.96 seconds**: B2, B1, and occupied-cell fallback suites. This includes actual evaluator-row validation, unchanged operational thresholds, tiny bitwise interrupted/uninterrupted parameter and telemetry parity, archive preservation, source/config binding, start limits, and bounded cleanup. The owner reports 84 focused tests; this audit independently ran the 52 directly affected tests.
- **17 full-worker mocks pass**, plus a direct watchdog-cancellation race check. Dict, Volume, clock, processes, and kill paths are local fakes; the supervisor receives the fake clock and kill function explicitly. No actual trainer subprocess or remote method was called by the harness.
- All **eight package file hashes** and the **memsub source-tree hash** match `SHA256SUMS-b2-package-v0.3.txt`. Shell syntax passes. Memsub remains `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`.
- All five B1 evaluator rows, including initialization, satisfy the amended schema. Four valid threshold cases retain the registered positive/negative decisions. All **nine prior malformed-result cases** return INVALID.

`focused-tests.log`, `package-verification.json`, `independent-worker-checks.py`, and `independent-worker-checks.json` retain the checks. The exact bound package files are copied under `candidate/`; the isolated snapshot path and commit are recorded separately. Earlier audit reports and reproductions remain unchanged in their own report directories.

## Blockers resolved

Trainer ownership now begins before the child watchdog is armed. A failed watchdog creation kills and reaps the trainer. Polling errors clean up the child and both armed guards. A ProcessLookupError during a kill race preserves the original polling error, reaps the child, and cancels both guards. Watchdog cancellation independently tolerates the same exit race and still waits. No worker mock leaves a trainer running.

The initial campaign-marker commit must succeed before training. Both a failed initial commit and a commit that leaves less than the registered 900-second startup minimum refuse before trainer creation. Periodic/final commit errors are counted. The delayed periodic-commit case still reaches the child budget, kills/reaps the trainer, and returns a timeout.

Pre-checkpoint artifacts and post-checkpoint telemetry are archived before restarting or rewriting. Foreign/unidentified state refuses. The checkpoint binds campaign name, memsub, script, base manifest, and exact PilotConfig. The Volume parent additionally binds the original campaign deadline and identities. Full-worker cases verify start-1 rejects a populated directory, a legitimate second start succeeds under the matching marker, and a second start with a foreign marker refuses. Exhausted starts, bad versions/deadline, insufficient post-setup time, and expired worker entry all refuse without training.

Results require each registered evaluation exactly once, valid integer counts totaling 256, accuracy/count consistency, 64 episodes, chance 1/64, and finite/ranged routing and fill measures for both final conditions. The significance claim is removed. The operational criterion remains final correct >=12/256 and correct(none)-correct(bank_derange)>=6. Passing is exploratory evidence for this variant/recipe/seed; routing support alone does not show useful retrieval.

## Exact launch scope and remaining limitations

The proposed scope remains one B2 arm, seed 0, 1,500 optimizer updates, evaluation every 100, checkpoint every 50, original filler curriculum 0 then 40 at update 1,000, and a final paired bank-derangement evaluation. Resources remain one L40S container, four CPU cores, 32 GiB, at most three admitted starts / two configured function retries, one immutable 23,400-second campaign deadline, local client lifetime 23,640 seconds, and one 300-second cleanup budget. No extra arm/seed, deadline extension, independent relaunch, merge, or integration is cleared by this audit.

The conditional **compute reservation is $16.2442476** within the requested $17. CPU overuse and app-stop latency remain external assumptions. Persistent Volume storage and transfer are excluded from that compute arithmetic; retain an explicit allowance for them in the $17 request and state retained-storage scope. The estimate of approximately $11 / 4.4 hours remains unprofiled for the long-input fallback phase. This is not a guaranteed external billing ceiling or a throughput result. Current resource and storage/transfer rates are documented by [Modal pricing](https://modal.com/pricing); the detailed calculations and operating assumptions are retained in the v0.1 audit.

CPU mocks do not prove real Modal preemption, watchdog scheduling, or successful remote checkpoint persistence. A checkpoint being written differs from it being committed. The Dict caps admitted workers, not every possible billed container startup. Preserve partial/replayed trajectories, source identity, checkpoint boundaries, terminal failures, and shutdown/billing evidence. If the final function refuses or raises without a tar, use read-only Volume retrieval after shutdown verification; do not launch a collection GPU. Normal completion still requires both launcher exits, a valid artifact audit, and stopped/unlisted app with zero tasks and containers.

The historical no-fix reference ran on A100, while B2 proposes L40S; matching recipe and data seed is not bitwise cross-GPU parity. B1's short train/dev length mismatch does not demonstrate that 100-update learning was impossible. Neither a B2 pass nor failure establishes a general claim about Qwen.

## Handoff

CPU package CLEAR applies only to the exact audited bindings. The owner must confirm the audited HEAD/bindings and a fresh channel read, then obtain the user's scoped $17 approval before paid execution. Any new code, scope, cap, deadline, or restart policy requires the relevant check before use. No GPU or paid call occurred in this audit.
