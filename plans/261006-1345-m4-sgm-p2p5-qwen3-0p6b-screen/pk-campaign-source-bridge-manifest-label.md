# P2.5 Amendment PK — source bridge: manifest backbone label (metadata-only)

Requested by codex 21585 (nonblocking provenance defect) / 21596 (bind and audit before the campaign).

## What changed
- Commit `fd0c1ec`, file `memsub/sgm/synthetic_pilot_run.py` only (the other two files in that commit are the
  new control-plane logic and its tests).
- `run_pilot`'s `run_manifest.json` field `backbone` was the hard-coded text
  `"tiny-qwen3-random-v1 (frozen, random init seed 0)"` for EVERY backbone. It is now `_backbone_label(pcfg)`:
  - `backbone == "tiny"` → the identical text (tiny manifests stay byte-identical; tested);
  - `backbone == "qwen3-0.6b-base"` → `Qwen/Qwen3-0.6B-Base@da87bfb608c14b7cf20ba1ce41287e8de496c0cd (frozen,
    pinned, sha256-checked)` from the pinned `QWEN3_0P6B_BASE` constant;
  - anything else raises.

## Why it is metadata-only
- The value is written into `run_manifest.json` and nowhere else; nothing reads it back for computation.
- No change to model build, training, evaluation, rows, metrics, telemetry, checkpoints or seeds. The tiny-CPU
  parity against the profiled reference stays bitwise, and the full SGM suite passes (package evidence).
- The per-cell output validator does not compare this field (it binds `pilot_config`, `memsub_source_sha256`
  and `final_eval_seed`), so old and new manifests validate the same way.

## Preserved evidence (unchanged bytes)
- The 10 completed PK-proof manifests under
  `p2p5-pk-proof-v1/volume-evidence/p2p5-pk-proof-v1/{A,Aprime,B,C,D,E}/cells/*/epoch-*/attempt-1/out/run_manifest.json`
  keep the stale tiny label. Their actual pilot_config (`backbone: qwen3-0.6b-base`), result_label, pinned
  model/source identity, Qwen geometry, payloads and the frozen tensor registry establish that they are Qwen
  runs (codex terminal audit 21585). They are covered by `SHA256SUMS-volume-evidence.txt` and are never rewritten.

## Source identities
| | memsub source sha256 |
|---|---|
| PK proof (frozen, audited) | 2e422cea… |
| after the label fix (campaign) | bound in the campaign registry / output schema / runner identities (package) |

Campaign registry and output schema were regenerated after the label fix and bind the post-fix source; the
proof registry/schema keep their proof-time binding.
