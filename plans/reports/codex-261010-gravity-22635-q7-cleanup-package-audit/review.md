# Q7 cleanup package audit: REVISE

Reviewed package at main commit `f5ffa48`, script SHA256 `849657f018331cd8ab5cc3f3088a6a3b447504ba1c09b74b61bc20f925a60db0`. User #gravity 22634 authorizes local merge and Q7 cleanup only. Claude owns execution and merge; this audit removed nothing. Q3/Q4/Q5 remain unselected.

The package pins the sealed 136-directory inventory and whitelist, checks directory identities and no-follow contents, restricts symlink targets to the candidate set, detects current process users, and verifies all 50 retained mutation logs. The current host reports `shutil.rmtree.avoids_symlink_attacks == True`. No remote service mutation is reachable from this script.

Independent checks passed: actual default dry run, removal sentinel, simulated unexpected path, changed pinned inode, actual child process with cwd inside a candidate, simulated retained-log hash corruption, and rejection of `--execute Q5`. See independent-results.json, independent-probes.py, and receipts. No Q7 target was changed; removal was never reached.

Two changes are required before removal:

1. Global preflight checks identity/content/use only once. Add a per-root identity/content/use guard immediately before each rmtree call, retaining the original candidate set for symlink checks. Record and stop at the first mismatch. This reduces the gap between checks and removal; it does not establish exclusive filesystem access.
2. Receipt save currently calls write_text directly. Use a temporary file, flush/fsync, atomic replace, and directory fsync. Persist the current path before removal and the completed path afterward. A refusal or partial failure must leave a valid receipt.

Sent REVISE in #gravity 22637. These package fixes are within the user's existing Q7 authorization; no new user approval is needed. Review the repaired script and fresh dry-run/refusal evidence before Claude executes. Local merge is independently authorized and awaits Claude's per-test baseline/candidate comparison plus focused changed memsub/default-policy validation. This report does not clear merge or claim its tests completed.

Protected copies and source bindings: previous sealed inventory audit, retained logs, B1/B2/B3 artifacts, shared memsub-artifacts volume and HF cache remain protected. No new training, model evaluation, remote deletion, push or publication was performed.
