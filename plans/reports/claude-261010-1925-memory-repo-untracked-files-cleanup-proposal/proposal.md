# memory repo — untracked files cleanup proposal r1 (nothing changed yet)

User 22711 "ok propose" (after claude 22701 offer). Scope: the 351 untracked `git status` entries on mvp @1957146
(27,661 files, 2,437 MB). Read-only inventory: `untracked-files-read-only-inventory.py` → `untracked-inventory.json`
(per entry: size, path refs + sha256 bindings from tracked files, byte-duplicates). No file was moved, edited or deleted.

## What is there
| Group | Entries | Files | MB | Notes |
|---|---|---|---|---|
| codex audit dirs `plans/reports/codex-*` | 265 | 27,195 | 851 | codex-owned; 60 sealed (SHA256SUMS); 15,087 files / 351 MB are preserved pytest temp outputs; 8,754 files (16 MB) are byte-identical to blobs already in git |
| run evidence in 5 closed plan dirs (P2C/P2D/P2G, P2.5 screen, readout probe, taskhead screen, info probe) | 84 | 260 | 1,586 | every entry referenced by tracked reports/configs; all hash-bound; only local copy for some |
| mine: `plans/reports/claude-261005-2352-p2d-…-recompute.{py,out}` | 2 | 2 | 0.01 | identical copies already committed (cb452fb, `p2d/step2-full-v1-r2/analysis-sources/`) |

Run evidence split: 118 text files (json/jsonl/log/md/txt, 11.7 MB; secret-pattern scan clean) + 142 binaries
(.pt 95 / .safetensors 41 / .npz 3 / .bin 3, 1,574 MB). 684 MB of the P2.5-screen binaries are extra identical
copies (e.g. one `trained_parameters.safetensors` in 7 attempt dirs). Disk: 483 GB free → space is not the issue;
the issue is a noisy `git status` and evidence that a push/fresh clone would not carry.
Code dependence: one test reads `p2g-selective-write-v1/launch_provenance.json` only if present; configs
`m4_sgm_p2c_inputs.json`/`m4_sgm_p2g_inputs.json` and `scripts/sgm-p2g-readings.py` cite run dirs by path.

## Proposed (user picks IDs; codex reviews first)
| ID | Action | Effect | Rec |
|---|---|---|---|
| U1 | `git add` my 2 files at their current path | no new git storage (same blobs); path refs stay valid | yes |
| U2 | `git add` the 118 run text files (list + sha256: `u2-run-text-files-to-commit.json`) | bytes unchanged; reports/configs resolve on a clone | yes |
| U3 | keep the 142 binaries local; add dir-scoped `.gitignore` rules (`*.pt *.safetensors *.npz *.bin` in the 5 closed plan dirs; 0 tracked binaries there) per the existing "large capture mirrors" convention; exact paths + sha256 committed in `u3-run-binaries-local-only.json` | `git status` quiet; nothing deleted; hashes recorded in git | yes |
| U4 | codex's 265 dirs: codex decides (e.g. commit text records + ignore the rest, and/or drop its 351 MB pytest temp copies under a new sealed manifest) | codex-owned; I do not touch them | codex |

Not proposed: deleting the 1.57 GB binaries (hash-bound closed-line evidence, some only copies, disk not short);
hard-linking duplicates (frees ~0.7 GB, not needed).

Execution after approval: one commit for U1–U3; check `git status` lists only codex dirs (or nothing, after U4);
rerun the hygiene test + the p2g test; codex audits. No push unless asked.

## Unresolved questions
- User: which of U1–U3?
- codex: U4 for its own dirs?
