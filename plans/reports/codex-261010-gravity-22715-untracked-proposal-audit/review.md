# Untracked artifact proposal r1: independent review and U4 recommendation

Reviewed #gravity 22715 at local `mvp` commit
`8607b216203725ee05642430f93a5ada190af4ea`. The proposal inventories the earlier
`1957146` snapshot. User 22711 authorized a proposal. No U1–U4 execution or push
was selected. This review created its own evidence files only; it did not stage,
delete, move, change an ignore rule, or rewrite an existing audit artifact.

**Recommendation: U1 and U2 are technically ready; retain U3 locally with exact
path ignore rules; use the non-destructive U4 option below. Revise r1's wording
and bind this concrete option in r2 before asking the user to select IDs.**

## U1–U3 verification

- The proposal's six-file SHA256SUMS verifies. All 2 U1, 118 U2 and 142 U3
  allowlist paths, sizes and SHA256 hashes match the current regular files.
  No path appears in two lists.
- Both U1 files already have identical tracked Git blobs. Adding these paths
  would reuse the blobs; path/tree/commit metadata still adds some storage.
- U2 JSON and JSONL parse strictly. The inspected U1/U2 text has no matches for
  the token/private-key patterns recorded in the audit script. This is a bounded
  pattern scan, not exhaustive secret detection.
- All 142 U3 binaries were hashed in full. Keep them in place. The alternative
  `u3-proposed-exact-ignore-rules.txt` covers only those 142 paths, avoiding a
  suffix wildcard. Read-only Git ignore checks match every selected binary,
  leave the tested future outside paths visible, and cover no tracked file.
- Committed text, inventories and hashes would travel with a clone. Missing
  local binaries, retained snapshots and external artifacts still limit replay
  and full audit verification. Replace r1's claim that reports/configs simply
  resolve on a fresh clone with this narrower portability statement.

## Concrete U4: commit records, retain all local contents

The original 265 Codex entries are **114 directories and 151 loose files**.
The no-follow catalog records 27,424 regular files / 853,613,163 bytes plus 204
symlinks, including files already ignored by Git. This has a broader scope than
r1's Git-visible 27,195 files / approximately 851 MB, so the totals are not a
contradiction. These are workspace evidence; authorship does not grant disposal
authority.

The recommended U4 action has **zero deletions**:

1. Commit the exact 1,197 direct text records at their existing paths, totaling
   13,604,006 bytes, from `u4-top-level-text-records-to-commit.json`. Its paths,
   sizes and SHA256 hashes are pinned. Strict JSON checks and the recorded
   secret-pattern scan found no exclusions.
2. Commit the catalog, symlink inventory, exact retained-root list, review and
   proposal metadata. This new review directory is outside r1's snapshot;
   include it explicitly in r2's metadata allowlist rather than silently
   expanding the original 265-entry list.
3. Retain **all** nested snapshots, binaries, logs and saved pytest outputs
   locally, including the approximately 351 MB of saved test copies. Preserve
   every historical checksum list and its current target bytes unchanged.
4. Use the 265 exact root rules in `u4-proposed-exact-ignore-rules.txt` for the
   retained remainder. Explicitly stage the approved text allowlist before or
   with those rules (`git add -f` if necessary). Use no blanket `codex-*` rule;
   future audits must stay visible.

This is a text-record packet with a catalog of retained dependencies. It is not
a complete portable audit bundle: some committed checksum lists refer to local
nested or external files. Do not describe a fresh-clone checksum failure caused
by an intentionally untracked dependency as a newly damaged historical audit.

## Historical seal limitations recorded, not repaired

The catalog contains 77 checksum-list files in 60 of the original entries.
Running each from its own directory gave 52 successful checks and 25 failures.
Those raw results mix relative-path context, historical dependencies and mixed
metadata; they are not a count of corrupt audits.

The contextual content check verified 2,956 file-checksum records at existing
repository/snapshot paths and found the expected bytes in named retained copies
for another 28. It left 31 historical records unresolved: 18 have a different
current candidate file, and 13 have no candidate in the checked contexts/copies.
Eleven other lines are `memsub_source_sha256` metadata, not file-checksum lines;
their aggregate source fingerprint was not recomputed. This is content coverage,
not 77 successful native `sha256sum -c` checks. See the per-record ledger and
unresolved list. No old content or seal was rewritten to make a check pass.

## Required r1 corrections and execution boundary

- Replace “265 audit dirs” with 114 directories plus 151 loose files; clarify
  that “60 sealed” means 60 entries containing 77 checksum-list files.
- Replace “every entry referenced; all hash-bound.” In r1's own 84 run-entry
  inventory, 46 lack a tracked full-path match and 14 lack a detected hash-bound
  file. Basename mentions may still exist; these are search findings, not proof
  of no reference anywhere.
- Replace “codex decides” with a concrete U4 recommendation subject to the
  user's selection. Remove the saved-test-copy deletion option from this packet.
- Preserve the separate Q3/Q4/Q5, trained-worktree-weight and shared-cache holds.
  No deletion, extra compute, push or publication is part of this proposal.

If the user selects the amended IDs, execution should recheck exact allowlist
hashes, stage only approved paths, inspect the staged diff, run the existing
hygiene and affected P2G checks, and produce a receipt for independent review.
Until that selection, all lists and ignore rules here are proposals only.
