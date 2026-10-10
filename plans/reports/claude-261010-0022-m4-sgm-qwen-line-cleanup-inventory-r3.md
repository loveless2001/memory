# M4-SGM frozen-Qwen line — cleanup inventory r3 (after B3; proposal, nothing evidence-bound deleted)

r3 supersedes r2 (kept unchanged). User 22606: "Ok stop, review and clean up". r2 round: user chose **Q1 only**
(22370, executed, receipt 4df48f1, codex PASS 22373); Q3/Q4 were not approved and are re-offered here with B3's items.

Stop check (2026-10-10 ~07:40Z): no non-stopped Modal app; no B3 watcher/collector process; worktree clean at 8bbb703
apart from the three hash-bound `trained_parameters.safetensors` (B1/B2/B3).
Done without approval (session-private, never referenced): my scratchpad copies of B3 progress checks 1–2.

## Proposed (needs user IDs; codex reviews first)
| ID | What | Where | Size | Retained copy |
|---|---|---|---|---|
| Q3 | Volume `memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1` (re-offered) | Modal | ~35 MB | codex wait38/41/42 mirrors + worktree `b2-resume-v1/volume/` (r2 Q3) |
| Q4 | 39 Dicts with `p2p5` in the name (r2's 38 + `m4-sgm-p2p5-b3-shift2-fill-long-starts-v1`) (re-offered) | Modal | tiny | r2's 38 exported by codex (22364); B3 Dict to be exported to JSON before deletion |
| Q5 | Volume `memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1` | Modal | 59,598,282 B, 11 files | codex `codex-261010-gravity-wait55-b3-terminal-audit/volume/` holds all 11 (sizes match, codex-hashed, incl. `resume.pt` step 1500 c9bb2293…); worktree `b3-run-v1/volume/` holds the 10 non-checkpoint files |
| Q7 | `/tmp/b3-mut-*` (136 dirs: mutation-harness tree copies, pytest basetemps, logs) | local `/tmp` | ~63 MB | not evidence: mutation results v1–v5 JSONs are in git; codex journals 22508/22513 cite paths only |

Execution after approval: one fail-closed script under a new receipt dir. Re-list and compare names/sizes with the
local copies before each `modal volume delete`; export Dicts before `modal dict delete`; take a pre/post size receipt
for Q7. Codex audits the receipt.

## Keep (not proposed)
- Q2 HF cache Qwen3-0.6B-Base (shared with latent-dream), `memsub-artifacts:m4-sgm/p2p5-*` (only copy of intermediates),
  `memsub-hf-cache` and the non-M4 reader Volumes.
- Stopped app records (`ap-uV0nVE4w…` etc.): Modal keeps stopped apps; there is nothing to delete.
- Worktree + branch `m4-sgm-occupied-fill-v1` (B1–B3 records), the untracked B1/B2/B3 safetensors (hash-bound),
  probe `features.npz` (hash-bound, not in git), all git-tracked records, and codex-owned report dirs.

## Unresolved questions
- User: which of Q3/Q4/Q5/Q7 (or none)?
- Merge `m4-sgm-occupied-fill-v1` into `mvp` or keep it separate (open since r2)?
