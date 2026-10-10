# Untracked files cleanup proposal r2.1 — addendum to r2 (240b814, kept unchanged)

Applies codex 22723 (review of r2). IDs U1–U4, lists, rules and recommendation (all four, zero deletions) are
unchanged from r2. Proposal only: no staging, ignore edit, deletion, compute or push.

## 1. Dry-run evidence defect (mine) — fixed in v2
r2's `u1-u4-combined-ignore-and-allowlist-dry-run.py` deleted the temporary rules file before the tracked-collision
check, and did not check git's return code, so r2's `tracked_matched_by_rules: []` was not evidence.
v2 (`u1-u4-combined-ignore-and-allowlist-dry-run-v2.py`): rules file removed only in `finally`; each git call must
return 0/1 and the rules file must exist, else it raises. Result (`u1-u4-combined-dry-run-v2-result.json`):
407 rules present to the end; 0 tracked files matched; 142/142 U3 binaries matched; 1,342 files / 36,053,921 B to
commit (1,197 need `add -f`); 0 untracked left visible in the all-four simulation; strict JSON clean.
Negative control: a `/README.md` rule is detected; a missing rules file raises. Codex's independent check (22723)
also found 0 collisions.

## 2. Execution checks (replaces r2 "git status must be empty" before commit)
1. Re-verify path/size/sha256 for every file of the selected IDs.
2. Stage only the selected paths (+ `.gitignore` sections for selected U3/U4, + receipt). Before commit: the staged
   path set must equal the selected allowlists exactly (`git diff --cached --name-only`).
3. Commit, then: tracked tree clean; remaining untracked paths reconciled against what is expected (unselected IDs,
   future audit or receipt dirs). Zero untracked is expected only if all four are selected, for this snapshot.
4. Hygiene test + `tests/test_sgm_p2g_observer_runner_and_preflight.py` under systemd-run caps; receipt; codex audit.
No push unless asked.

## Unresolved questions
- User: which of U1–U4?
