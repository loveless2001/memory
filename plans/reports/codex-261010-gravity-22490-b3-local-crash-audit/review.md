# B3 local CPU crash audit

Scope: response to #gravity user mention 22490 and Claude report 22501. Read-only incident/source review, with retained copies written only to this new report directory. No model load, numerical test, GPU, deployment, spawn, or cloud operation by this audit. Claude owns the ongoing repair and test rerun in the occupied-fill worktree.

The snapshot was taken at 2026-10-09 20:44:55 UTC (2026-10-10 03:44:55 Bangkok), worktree HEAD c6a3ae48fe618e76e860d3066075a2bf243a9c8f. B3 implementation files were untracked and actively being edited/mutation-tested; HEAD alone does not bind them. Per-file snapshot hashes and original paths are in capture-manifest.json. This is an incident review, not B3 package clearance.

## Confirmed evidence

- The previous boot's kernel journal records a global OOM at 2026-10-09 20:24:01 UTC. It killed Python PID 280293, with anonymous resident memory 5,601,360 kB and total virtual memory 8,786,008 kB. The boot log then ends at 20:25:42 UTC; the next boot begins at 20:37:13 UTC. The kernel record independently establishes the OOM and killed Python process. It does not, by itself, establish that the kernel directly killed both Claude sessions or prove why the subsequent restart occurred.
- Claude's retained runner-as-found-M4.py has cleanup app stop without --yes and an uncapped loop appending each verification result to rec["checks"]. The saved reproduction invokes cleanup with a no-op sleep and a real clock. This combination explains unbounded record growth while a deployed app remains unresolved. The reported 90,658 checks / 264 MB in two seconds was not independently rerun.
- The repair source inspected before mutation execution restored --yes, capped the default cleanup loop at 17 checks, and advanced a fake clock in the relevant tests. The separate frozen-clock/no-op-sleep regression aborts its verifier after 50 calls, so removing the cap has a bounded test failure.
- The retained b3-pytest.log reports 32 passed in 10.62 seconds. This is Claude's test artifact; this audit did not execute that suite or bind its execution to a final immutable source manifest. The mutation harness was still running during inspection. A live-runner snapshot can intentionally contain a current mutant and is not proof of final restoration.

## Repair follow-up sent in message 22506

1. The inspected harness deletes BACKUP before JOURNAL in both restore paths. A kill between those two operations leaves a journal referring to a missing backup, so the next run cannot restore as advertised. After verified durable source restoration, retire the journal first and then the backup; use durable atomic metadata updates. A disposable source tree would avoid leaving the shared worktree mutated at all. The present on-disk journal is deferred recovery on a later invocation, not automatic source restoration at the time of a kill.
2. The inspected harness calls every nonzero return code except 137/-9 CAUGHT. That can count systemd launch errors or pytest collection/infrastructure errors as detected mutants. Require an ordinary test failure with the expected failure evidence; classify infrastructure errors separately. The new KILLED status is an appropriate distinction for killed/timed-out runs.

The driver invokes pytest through systemd-run with MemoryMax=2000M, MemorySwapMax=0 and a 300-second KILL timeout. This audit read the command definition; it did not independently prove cgroup enforcement. Its capture_output buffer remains outside each child's memory scope. Whole-driver containment or bounded file output would make the containment claim stronger.

## Current boundary

The OOM incident and saved M4 source support Claude's local test-harness diagnosis. The revised cleanup logic addresses that loop mechanism. Final source restoration, all-mutant evidence, crash recovery, isolation/containment and the complete B3 implementation/ledger still require review after Claude's repair handoff. Paid package clearance and numerical/cap approval remain pending. No new run or paid action was authorized or performed here.

Identity: there was no previous identity in this context to reclaim. The user was asked to name the instance via its status pill. The current MCP registration independently returned codex-gravity; no historical sender was claimed from channel history.
