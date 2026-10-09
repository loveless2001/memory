# M4-SGM frozen-Qwen line — cleanup inventory (proposal; nothing audit-bound deleted yet)

User 22357: "stop and write up then clean up". Scope: this Qwen line only (codex 22359).
Stop check 2026-10-09 17:3xZ: `modal app list` shows no non-stopped app. No probe/collector process is running locally.
Already done (not evidence): the session scratch copy of the B=1 smoke was removed. Its evidence copy stays in `r2-smoke-b1-k1/`.
Context: the earlier cleanup (receipt `claude-261009-0237-gravity-cleanup-receipt`, groups A–D, 16.5 GB) already removed local intermediate `gen-*.pt` checkpoints, probe intermediates and CPU fixtures. Disk free is 479 GB, so further cleanup is about tidiness, not space pressure.

## Proposed (needs user OK; codex reviews first)
| ID | What | Where | Size | Why removable | Retained copy |
|---|---|---|---|---|---|
| Q1 | `.venv-gpu` (uv env, torch 2.7.1 cu126) | `memory/.venv-gpu` | 5.2 GB | not evidence; only this line's local GPU scripts use it; re-creatable | recipe in repo (pinned versions recorded in launch identities) |
| Q2 | HF cache Qwen3-0.6B-Base | `~/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B-Base` | 1.2 GB | only this repo's Qwen line uses it locally (Modal images bake their own weights); re-downloadable at pinned rev da87bfb6 with sha checks in `pinned_pretrained_qwen3_backbone.py` | HF Hub |
| Q3 | Modal Volume `memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1` | Modal (dedicated to B2) | ~35 MB | redundant: complete local copies exist | codex `wait38/…/resume.pt` (step 750, cd1a7e72), `wait41/volume/B2/resume.pt` (900), `wait42/volume/B2/{resume.pt (1500), trained_parameters.safetensors}` + worktree `b2-resume-v1/volume/` |
| Q4 | 38 Modal Dicts of this line (names containing `p2p5`: reaper proof, P2.5 profile/proof/campaign guard·admission·control, readout-probe, Stage A, B1, B2 starts) | Modal | tiny | workspace clutter only; terminal audits done | export each Dict to JSON under a new receipt dir before deleting |

## Keep (not proposed)
- **Remote `memsub-artifacts:m4-sgm/p2p5-{l40s-profile-v1,l40s-profile-v2,pk-proof-v1,qwen3-0p6b-screen-v1,readout-probe-v1}`.** This is the ONLY copy of the intermediate checkpoints, whose local copies cleanup A/B removed. Est. ~15 GB, from the earlier local copies' sizes. Deleting it would be irreversible loss of audit-bound evidence; it should go only if the user explicitly drops the binaries.
- Local untracked finals (~1.1 GB: PK proof captures, campaign/probe finals, Stage A, smoke). They are hash-bound and used by local replays.
- All git-tracked records, the r1 crash logs (empty files are evidence), worktree + branch `m4-sgm-occupied-fill-v1` and the two small duplicate `trained_parameters.safetensors` (8.6 MB).
- Codex-owned dirs (e.g. `codex-261008-p2p5-pk-21911-run-check`, 72 MB): codex decides.
- Non-Qwen M4 items (P2/P2D/P2G/P2C runs, logs, Dicts): out of scope.

## Execution (after approval)
One script under a new receipt dir:
- Q4: export the Dicts first, then delete.
- Q3: compare the remote listing (names/sizes) with the local copies + SHA256SUMS before `modal volume delete`.
- Q1/Q2: `rm -rf` with a pre/post size receipt.
Codex audits the receipt.
