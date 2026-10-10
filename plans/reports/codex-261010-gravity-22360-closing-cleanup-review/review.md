# Independent closing-writeup and cleanup review

Reviewed for #gravity 22360–22364. The user closed the frozen-Qwen sidecar line in 22357. This review performs preparation and verification only; Claude owns the proposed deletion and its receipt after the requested Q-ID approval.

**Outcome:** the r3 writeup preserves the narrow negative result and the distinction between learned routing and successful oracle controls, and resolves the two r2 editorial details. The concrete Q1/Q3/Q4 cleanup script and its saved read-only dry run pass this scoped review. Q1, Q3 and Q4 have retention records. Q2 is withdrawn because its model cache is shared with latent-dream. No remote object was changed, no environment was removed and no numerical experiment was dispatched during this review.

## Writeup and scientific boundary

Reviewed copies of the owner's documents at commit `7821b75` are included here:

- `claude-261010-0022-m4-sgm-qwen3-0p6b-sidecar-line-closing-writeup-r2.md`, SHA256 `e8cade5af46a45f7a67579b86a9bff26cdb6c90dbef4680328f348b3a0da2c52`.
- `claude-261010-0022-m4-sgm-qwen-line-cleanup-inventory-r2.md`, SHA256 `e13e6bf9b069fdaa26dfa0c824e5cc0f2ad8d597e48cb8654fd1f1679e2808d8`.

The registered B2 endpoint remains a negative for the tested fill+anchor recipe, seed and held-out gate: 5/256 normal and 5/256 deranged. Equal counts do not establish identical predictions because per-example outputs were not saved. The CPU diagnosis establishes an open task-gradient path at initialization and suppressed reads/writes at the measured endpoint; it does not establish cause or timing. The retained step-750 checkpoint was not subjected to a new geometry measurement.

The P2.5 campaign's N32 learned counts 71/1024 and 60/1024 are distinct from the readout-probe population's residual-head counts 74/1024 and 65/1024. The latter are above chance; the taskhead probe did not demonstrate rescue. The oracle controls reached 100% and approximately 97.9%, so the closing claim applies to tested learned-routing/non-oracle recipes. The r2 writeup makes that distinction. The CPU crash statement also correctly separates the observed global OOM from the subsequent WSL shutdown whose trigger is unknown.

Two minor editorial details were reported in 22364: B1 completed its designed 100 updates, so “PARTIAL” should describe routing quality rather than incomplete execution; the displayed rounded cost rows sum to $162.08, while r2's headline says approximately $162.09. Owner writeup r3 at commit `0411ab2b3225e3beffec4903819eb7dd9f544292` resolves both. Its SHA256 is `fb61ad341db4a3017ec0a6ef4705e3e0a5aae4181b871350bbb8d0bbb2db0bdb`; a copy is retained here. B1 explicitly completed all 100 updates, and the total is stated as about $162 provisional. The main `M4-SGM.md` links r3. `cost-check.json` retains the earlier r2 arithmetic finding and the probe's app-attributed snapshot of $18.55304785. No settled invoice is inferred.

## Retention and deletion boundaries

| ID | Reviewed target | Retention evidence | Boundary |
|---|---|---|---|
| Q1 | `/home/lenovo/projects/memory/.venv-gpu`, 5,529,944,064 allocated bytes | `q1-gpu-environment.json` records Python and 40 installed packages; `q1-q2-paths.json` records the resolved path and size | Environment-only cleanup after the requested approval. Preserve the project `.venv` and this metadata. No rebuild was attempted; metadata capture is not a tested reconstruction. |
| Q2 | Shared HF model cache, 1,203,666,944 allocated bytes | The snapshot is `da87bfb608c14b7cf20ba1ce41287e8de496c0cd`; `latent-dream/src/kv_dreaming/runtime.py` uses the same model and revision through local HF loading | **KEEP.** Withdrawn from line-only cleanup. |
| Q3 | Modal Volume `memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1` | Complete `q3-complete-volume/` mirror, recursive listings before/after, and per-file hashes in `q3-file-verification.json` | Eligible under the requested Q3 approval only after a final remote identity/content check. Keep the mirror and previous checkpoint evidence. |
| Q4 | Exactly 38 named Modal Dicts | `q4-name-whitelist.json`, `q4-export-index.json` with object IDs, and one type-preserving JSON export per Dict under `q4-dicts/` | Use the frozen whitelist rather than a fresh substring search. Recheck IDs and contents before deletion; retain every export. |

### Q3 completeness

Capture completed at `2026-10-09T17:36:03.753325+00:00`. The recursive listing contained 18 entries: 14 files and four directories, all under `b2-run-v1/`. The before/after listings were identical. All 14 downloaded files passed size checks, have SHA256 records and match at least one previously retained local copy. Total file bytes are **34,361,985**, including empty start stderr/stdout files and archived routing telemetry.

The current remote `B2/resume.pt` is 25,159,637 bytes, SHA256 `443f041cae4efa21b7859415063c059248ce8fabe4f53b3f87c58d7c8f189634`, and passed ZIP CRC validation. Final `trained_parameters.safetensors` is 8,625,720 bytes, SHA256 `2149c97517ad0f844b30a82f52b0072090f02b1709809f6bac5f09afe107fdb3`. No checkpoint was deserialized and no training restore was attempted. This verifies file retention, not fresh-process continuation behavior.

Earlier step-750 and step-900 evidence remains in its existing audit locations. The dedicated B2 volume is distinct from `memsub-artifacts`; the latter's P2.5 prefixes contain retained intermediate checkpoints and remain KEEP.

### Q4 export completeness

The live list contained 42 Dicts; the frozen Qwen-line whitelist selected 38 and excluded four non-Qwen Dicts. All **430 entries** were exported using a type-preserving codec and passed encode/decode equality checks. Export hashes, object IDs and entry counts are in `q4-export-index.json`. This verifies lossless serialization of the observed values; it is not a remote delete/recreate test. Any pre-delete drift requires a refreshed retained export before deleting that object.

## Stop state and handoff

`apps-live.json` is the empty live Modal app list captured during preparation. The prior CPU terminal audit verified that the launcher, watcher and numerical worker had exited; no diagnostic rerun was authorized by the closing instruction. The capture script uses only read-only Modal listing/file/Dict APIs, with `create_if_missing=False`. `capture-summary.json` records zero remote mutations and zero compute dispatches.

This folder, all tracked records, the worktree and branch, crash logs (including empty files), local finals, older checkpoint captures, shared model cache, `memsub-artifacts` evidence prefixes and non-Qwen resources remain retained. The owner's execution should produce a bounded receipt with exact approved targets, pre-delete drift checks, local sizes and post-delete absence checks. Codex can independently review that receipt when posted. No deletion receipt exists from this review.

## Concrete cleanup script review (22365)

Owner commit `3bd0e1ed10e5fb1436975dca78e5a0ae374d5555` supplies `qwen-line-cleanup-approved-q1-q3-q4.py`, SHA256 `0fbc628461ebcd07ee34a2d5e671b1de51f5197a0e54bd014e619b342dfb3a7f`. Its source and saved dry-run receipt/summary are copied here. Python AST parsing passed. The installed Modal 1.5.1 CLI implementations confirm the script's Dict and Volume delete argument form, including `--yes`; these destructive commands were not invoked during this review.

The script accepts only a nonempty, duplicate-free subset of Q1/Q3/Q4. It checks that apps are stopped and the local Q3/Q4 backups still match their indexes. For Q4 it uses the frozen exact-name whitelist, requires the current object IDs and encoded items to match all 38 exports before deleting any, and checks absence afterward. For Q3 it checks the complete recursive listing against the retained snapshot and checks absence after deletion. For Q1 it requires an ordinary directory, checks process arguments for use of the environment, records size and disk space, and checks path absence afterward. Q2 and `memsub-artifacts` are outside its deletion targets. Ordinary exceptions halt remaining work and write the partial receipt in `finally`; this review does not authorize an automatic retry after a partial failure.

The retained dry run reports `status: OK`, `dry_run: true`, started `2026-10-09T17:40:36.860422+00:00` and ended `17:41:07.301813+00:00`. It verifies 38 unchanged Dicts and the identical 14-file Q3 listing; its Q1 size is 5,471,593,161 apparent bytes. The larger 5,529,944,064 value in this review is allocated disk bytes, so the two measurements are compatible. The dry run deleted zero objects. This is the owner's saved run, inspected independently; Codex did not rerun it.

No execution blocker was found within these exact targets and retained snapshots. The owner is awaiting the already-requested user Q-ID selection. The next action is the approved execution and a receipt review, without expanding the whitelist or removing KEEP evidence.

`manifest.json` and `SHA256SUMS` bind the retained artifacts in this folder; they exclude themselves to avoid circular hashes. The validation performed while creating the manifest checks the Q3 mirror and Q4 export hashes against their recorded indexes.
