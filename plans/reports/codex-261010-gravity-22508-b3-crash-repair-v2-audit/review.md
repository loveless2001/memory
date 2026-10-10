# B3 crash repair v2 audit

PASS for the local cleanup spin repair and the two harness findings in #gravity 22506. This does not clear the full B3 package, numerical execution, or a paid cap. Scope is the repair handoff in message 22508.

The five retained source/result files exactly match commit 218695024f52e298b9ae989e385c09267d4bf777 and the live occupied-fill worktree at capture. Full hashes are in source-manifest.json and match all five reported hash prefixes. The tracked working tree was clean at capture and after the independent checks. Changes from c6a3ae4 through 2186950 add only the B3 runner, training wrapper, tests and mutation harness/results; protected B2 sources and memsub are unchanged in that commit comparison.

## Confirmed repair

1. The cleanup runner includes --yes, a shared time budget and the independent check-count cap. At default budget 300 seconds / wait 20 seconds it admits at most 17 checks. The frozen-clock/no-op-sleep regression has a separate 50-call test guard, so removal of the production cap fails promptly.
2. The v2 harness writes mutants only to a temporary git-archive copy. It compares the B3 runner/train/tests with the worktree hashes before testing and verifies the same worktree files afterward. The journal/backup restoration machinery is gone, eliminating the shared-source restore-order hazard. A killed process may leave a disposable directory; it cannot leave a shared source mutated through this code path. Results are still written to the shared implementation directory, so the precise claim is that shared source files are not mutated.
3. Classification now requires rc 1 plus a FAILED test identifier belonging to the expected function set. A different failing function is WRONG_TEST; rc 1 without a FAILED record and collection/usage errors are INFRA_ERROR; 137/-9 are KILLED. Ordinary infrastructure failures no longer count as caught mutants.

## Independent verification

check-crash-repair.py extracts only cleanup_verify and classify from the retained source ASTs and uses standard-library fakes. It imports no repository, model, training, or cloud modules. Executed once under systemd-run with MemoryMax=256M, MemorySwapMax=0 and a 20-second KILL timeout; exit code 0. The process read its actual cgroup files and confirmed memory.max=268435456 bytes and memory.swap.max=0.

Four cleanup checks passed: successful --yes stop/verification; exactly 17 never-verified checks under frozen time/no-op sleep; missing---yes mutant remains unresolved and bounded; removed-cap mutant fails the independent 50-call guard. Seven classification cases passed, covering survived, expected failure, wrong test, rc-1 infrastructure failure, collection error, 137 and -9.

The retained mutation JSON is consistent with baseline 32 passed and 11/11 expected-function catches, each rc 1, with no killed/infrastructure outcomes. M8 actually failed the dedicated deadline_mismatch parameter case; M1/M2 failed the completed case; M3 the exception case; M10 the versions case. Source inspection confirms the first five worker cases exercise the respective guards. The user systemd journal independently corroborates baseline and M1-M11 scoped pytest launches at 03:50:06-03:52:11 Bangkok. This audit did not rerun the complete package suite or all 11 mutants.

## Limits and next handoff

- EXPECTED pins test function names, not exact parameter IDs; full parameter IDs are retained in the evidence. The actual recorded cases are appropriate. Pinning complete IDs would make future mutation classification more specific.
- Child pytest scopes carry the defined 2000M/zero-swap limits; parent capture_output remains outside those scopes. This is child-process containment, not a demonstrated whole-driver memory bound.
- The saved mutation JSON contains failure identities and summary tails, rather than complete per-mutant stdout/stderr or a execution-time source manifest. Its evidence is narrower than a fresh independent all-mutant replay.
- The retained-Volume measurement and complete implementation/ledger handoff remain separate package work. No model load, numerical training, GPU, deployment, spawn, cloud lookup or paid action occurred in this audit.

The earlier incident wording correction is accepted: the kernel proved a global OOM and killed Python process; the cause of the later restart and direct killing of either Claude session remain unestablished.
