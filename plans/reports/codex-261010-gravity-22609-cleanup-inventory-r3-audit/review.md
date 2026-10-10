# Qwen-line closure and cleanup inventory r3 review

**PASS for the candidate inventory and retained-copy checks. No deletion or merge clearance yet.**
Reviewed inventory r3 at main commit eaa018e (SHA256 32310eb6399986a8314d7a25b22dcfce9a66cc594d814a4f372ec4fe9a82c3eb),
B3 readout r2 at 8bbb703 (SHA a47bf23ae2a6a4d7bf0f950c82162b751209655c9902dcc27489a62e07a9dd95), and closing
write-up r4 at 8237fad (SHA 29cc3113362ca3b58e9becf1da2fd06a4447e24973ca84017bb313512c3d896a).
User #22606 closes this paid line and requests review/cleanup. Inventory r3 explicitly preserves the earlier
Q1-only selection and re-offers Q3/Q4; its deletion gate is a named user-ID selection, then a fail-closed receipt.
This audit is read-only and does not expand that selection, delete a resource or merge the branches.

## Closure and documentation

Fresh state capture 2026-10-10 07:36:30–07:37:24 UTC finds only stopped Modal apps with zero tasks and no containers.
The B3 terminal audit already established watcher exit and clean completion. No new training, deployment,
spawn, evaluation or restart was performed. The separate one-time billing wait #64 does not launch compute.

B3 readout r2 withdraws the unsupported parameter-freezing interpretation, separates training seed 0 from
reused development seed 4242, and identifies the previous-key probe's shift1/offline scope. Its negative screen
8/256 normal versus 8/256 deranged agrees with the independently sealed terminal audit. The r4 additions carry
the offline probe result and B3's narrow negative with causal questions left open, preserve prior revisions, and
retain a provisional total rather than claiming a settled bill. Existing older stage findings were not replayed.
M4-SGM.md explicitly marks P2.5 through B3 closed. These documentation changes pass review.

## Proposed objects and independent copy verification

| Candidate | Verified target | Current size/count | Retained evidence |
|---|---|---:|---|
| Q3 | `memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1` | 14 files; 34,361,985 B | Complete prior codex Q3 mirror; every current remote file rehashed and matched |
| Q4 | Fixed old 38 Dict names plus B3's start Dict | 39 Dicts; 433 entries | Fresh typed JSON exports here; all 38 prior object IDs/content unchanged; B3 agrees with terminal snapshot |
| Q5 | `memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1` | 11 files; 59,598,282 B | Sealed wait55 mirror including step-1500 checkpoint; every current remote file rehashed and matched |
| Q7 | Exact 136 existing `/tmp/b3-mut-*` directories | 52,383,240 B by `du -sb`; 52,354,966 regular-file B | 50 raw mutation logs retained here (71,677 B); source and v1–v5 result artifacts remain elsewhere |

Both Volumes' complete recursive file sets match their retained-copy manifests. Listings were stable before/after
the full streaming SHA256 checks; matching names/sizes alone were not used as copy proof. No extra Volume files
were omitted. The Dict exports preserve types, round-trip every item, and identify immutable object IDs.
The fixed Q4 allowlist equals the current p2p5 set, but future deletion must use that list rather than a substring
search. Current snapshots and export hashes are in `q3-verified-files.json`, `q5-verified-files.json`,
`q4-export-index.json`, and the per-Dict files.

Q7 is slightly smaller than the inventory's approximate 63 MB: the current apparent size is 52.38 MB (~49.96 MiB).
All roots are real directories owned by the current UID; device/inode identities and exact paths are recorded.
There are 520 nested symlinks, all pointing inside these candidate roots. No process was observed using these
paths via cwd/open descriptors. This is a point-in-time observation, not an execution lock. Deletion must never
follow symlinks or rely on a newly expanded wildcard. The previously session-private raw logs now have retained
hash-bound copies, so their disposal does not discard the only copy of failure output.

The shared HF cache, sole-copy `memsub-artifacts` intermediates, non-M4 resources, B1/B2/B3 safetensors,
previous-key features, all worktrees/branches, tracked files and codex-owned report directories remain protected.
No space-reclaimed claim is made: this audit deleted nothing.

## Required concrete execution package

Requested from Claude in #22611 before deletion clearance:

- Pin user-selected IDs, the two exact Volume names, the 39 named/object-ID-bound Dicts and exact Q7 path/device/
  inode list. Reject unselected IDs, newly appearing resources, symlink roots, changed targets or unexpected files.
- Immediately before each approved group/resource deletion, re-establish shutdown, rehash the complete local
  copies and exports, verify fresh remote file content/listing and Dict contents/object IDs, and recheck local use.
- Make a dry-run receipt that cannot reach deletion APIs. Actual deletion must fail closed on any mismatch;
  use noninteractive confirmation only for approved exact targets and record failures/partial success durably.
- Preserve the existing backups, new Dict exports and retained logs, use no-follow local removal, then verify
  absence of the exact deleted objects and record before/after size observations.

The inventory describes such a future script but does not itself provide one. Inventory PASS is not executable
package PASS. No script deletion path was exercised in this review. User ID selection and the concrete reviewed
script/dry-run are the next gates; approval is not inferred from the proposed objects. The user/Claude already
hold the selection question. Branch merging is independent and unnecessary for preservation or cleanup review;
both branches remain intact pending that separate decision.

All checks, exports, target manifests, input documents and retained raw logs are sealed by `SHA256SUMS`.
