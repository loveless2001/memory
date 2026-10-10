# memory repo — untracked files cleanup proposal r2 (nothing changed yet)

Supersedes r1 (`claude-261010-1925-…-cleanup-proposal/`, 8607b21, kept unchanged). Applies codex review 22720
(`codex-261010-gravity-22715-untracked-proposal-audit/review.md`, sha256 377742bc…879a, 24-file seal verified).
User 22711 authorized a proposal only. No U1–U4 execution, deletion, compute or push selected.

## Inventory (snapshot mvp @1957146; corrected per codex)
| Group | Entries | Files | Size | Notes |
|---|---|---|---|---|
| codex audit records `plans/reports/codex-*` | 265 = 114 dirs + 151 loose files | 27,424 regular + 204 symlinks (no-follow catalog, incl. git-ignored) | 853.6 MB | 60 entries contain 77 checksum lists; ~351 MB are saved pytest outputs |
| run evidence, 5 closed plan dirs | 84 | 260 = 118 text + 142 binaries | 1,586 MB | 38 entries have a tracked full-path reference, 46 do not (basename mentions may exist); 70 contain a file whose sha256 appears in tracked text, 14 do not |
| mine `claude-261005-2352-p2d-…-recompute.{py,out}` | 2 | 2 | 0.01 MB | identical blobs already tracked (cb452fb) |
Disk 483 GB free: space is not the problem; a noisy `git status` and records that a clone would not carry are.

## Proposed IDs (user picks)
| ID | Action | Files / size | Rec |
|---|---|---|---|
| U1 | commit my 2 files at their path (r1 `u1-claude-files.json`) | 2 | yes |
| U2 | commit run text records (r1 `u2-run-text-files-to-commit.json`; strict JSON + pattern scan clean) | 118 / 11.7 MB | yes |
| U3 | keep the 142 binaries local; add codex's **exact-path** ignore rules (`u3-proposed-exact-ignore-rules.txt`, 142 lines; replaces r1's suffix wildcards); hashes stay committed in r1 `u3-run-binaries-local-only.json` | 142 / 1,574 MB kept | yes |
| U4 | codex's non-destructive option: commit the 1,197 direct text records (`u4-top-level-text-records-to-commit.json`, 13.6 MB, `git add -f` since they sit in ignored roots) + codex review dir 22715 (catalog, symlinks, retained-root list, seal ledger; 25 files, 10.8 MB); retain ALL nested contents, binaries, snapshots and saved pytest copies locally; add codex's 265 exact root rules (`u4-proposed-exact-ignore-rules.txt`); no `codex-*` wildcard, future audits stay visible | 1,222 committed / ~840 MB kept | yes |
Zero deletions in any ID. Ignore rules go in root `.gitignore` under two commented sections, text exactly as codex supplied.

## My dry run of U1–U4 together (read-only; `git check-ignore --no-index` with the 407 rules)
- after committing the 1,342 allowlisted files (36.1 MB) + this r2 dir, 0 untracked paths would stay visible;
- all 142 U3 binaries matched; 0 tracked files matched by any rule; 1,197 U4 files need `add -f` (expected);
- strict JSON parse (hygiene-test rule) passes for every to-commit `.json`.

## Portability limit (replaces r1 "work on a fresh clone")
Committed text, inventories and hashes travel with a clone. Replay and full checksum verification still need the
retained local binaries/nested files and external copies (Modal Volumes). A fresh-clone checksum failure caused by an
intentionally untracked dependency is not a newly damaged audit. Codex's seal ledger records existing limits without
repair: 2,956 file records verify at current paths, 28 in retained copies, 31 historical records unresolved, 11 lines
are source-fingerprint metadata.

## Execution after selection
Re-verify every allowlist path/size/sha256 → stage only those paths (+ `.gitignore`, r2 dir) → inspect staged diff →
`git status` must be empty → run hygiene test + `tests/test_sgm_p2g_observer_runner_and_preflight.py` under
systemd-run caps → one commit + receipt → codex audit. No push unless asked. Q3/Q4/Q5, worktree weights and the
shared HF cache stay protected.

## Unresolved questions
- User: which of U1–U4?
