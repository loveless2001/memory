# Q1-only cleanup receipt: independent terminal audit

**PASS for the authorized Q1 deletion.** User #gravity 22370 approved only Q1. The owner's receipt at commit `4df48f1` records exactly that selection, successful execution and no Q3/Q4 deletion. Independent live checks confirm that `/home/lenovo/projects/memory/.venv-gpu` is absent, the complete B2 volume still matches its retained mirror, all 38 frozen Dicts retain their object IDs and contents, and all 72 previously retained backup artifacts still pass their hashes.

The Qwen experiment line stays closed. This audit performed read-only verification and wrote local audit records. It removed no resource, dispatched no compute and ran no checkpoint/model evaluation.

## Receipt and scope

`summary.json` has `approved_ids: ["Q1"]`, `dry_run: false`, `status: "OK"` and only a Q1 result. `receipt.jsonl` contains one precheck event and one Q1-delete event, with the exact approved environment path. `q1-run.log` ends with `EXIT=0`. The copied source accepts only Q1/Q3/Q4 and gates their separate deletion branches on the selected IDs.

Receipt hashes match the owner's post:

- `receipt.jsonl`: `83f75a7176974126b476be44ccfc58aa67b4e5a84b8d664cd685fc83e4e63d25`.
- `summary.json`: `32052554208776aafba3b387f2d5de43d859a6b9cf58eed08ee3472ebda42fd5`.

The main `.venv`, shared HF model cache, shared uv cache and occupied-fill worktree still exist. `.venv-gpu` has neither a directory entry nor a dangling symlink. The retained environment package/Python metadata remains hash-intact in the earlier review folder.

## Independent retained-resource checks

The live read-only verification completed at `2026-10-09T17:53:43.260465+00:00`; its process exited 0.

- Q3: the recursive B2-volume listing equals the retained capture. All **14 live files / 34,361,985 bytes** were streamed through SHA256 without writing to the volume; every hash and size equals the retained mirror index, including empty logs and archived telemetry.
- Q4: all **38 Dicts / 430 entries** retain the exported object IDs and their exact type-encoded contents. No Dict creation, update or deletion occurred.
- The prior review manifest's **72 local artifact hashes** still pass.
- `memsub-artifacts` remains listed. Its large checkpoint prefixes were not recursively downloaded or rehashed in this audit; the approved Q1-only script has no deletion target for that volume.

The metadata snapshots and per-object verification records are included here. `audit-summary.json` records zero remote mutations and zero compute dispatches.

## Space accounting

The Q1 receipt records 5,471,593,161 apparent bytes removed. Filesystem free bytes changed from 513,342,214,144 to 513,406,865,408 during the operation: a delta of **64,651,264 bytes = 61.65625 MiB**. This is the observed filesystem delta; it does not establish that 5.5 GB of unique physical blocks were reclaimed.

The owner's shared-cache explanation is consistent with the small delta, and cached `torch 2.7.1+cu126` files remain present. However, the deleted environment has no retained inode/link-count comparison, so this audit does not independently prove its exact cache-linking mode. The installed uv help states that Linux defaults to `clone`; the GPU cache library now has one link, while another CPU cached library has two. Those post-deletion observations cannot establish the former GPU environment's linking mechanism. Record the space delta as measured and cache-sharing attribution as an inference. The shared uv cache was outside Q1 scope and remains retained.

## Stop point

The authorized cleanup is complete. Q2, Q3, Q4, `memsub-artifacts`, worktree/branch, scientific records and backup/export folders remain retained. No additional deletion or retry follows this audit. The scientific result and approximately $162 provisional accounting remain as described in the closing writeup r3.

`manifest.json` and `SHA256SUMS` bind this audit folder's artifacts and exclude themselves. The report copies the owner's existing deletion receipt; it does not rerun that deletion.
