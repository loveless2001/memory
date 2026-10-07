# P2.5 readout-recipe rescue probe: frozen proposal v0.1 (EXPLORATORY)

Status: DRAFT for codex audit. User 21748 asked for this proposal ("write the probe then"). This document does NOT
authorize a launch. The launch needs, in order: codex proposal audit → implementation → local smoke → codex
implementation audit → the user's explicit cap.

Basis: diagnosis rev 2, codex PASS 21747 (`plans/reports/claude-261008-0127-p2p5-saved-evidence-diagnosis/`, d3d4999).
P2.5 outcomes stay as recorded: the original reading is `unavailable` and the post-hoc amended reading is `screen not
passed`. This probe never changes them.

## 1. Question
Under the otherwise-identical P2.5 recipe, does replacing the residual-head readout with the P2C task-head readout
(features = the memory reads at the selected layers only) improve learned N32 on frozen Qwen3-0.6B-Base? If it does,
does the improvement depend on the episode's own memory bank?

## 2. What it can and cannot show (codex 21745 #1)
- **Can show:** whether this changed readout recipe improves learned N32 on the known artifact population, and whether
  the taskhead model passes the registered bank-dependence check.
- **CANNOT show** that the phase-1 local route was the main blocker, and cannot rule it out either. The task head also
  changes feature dimensions, head initialization, gradient routes and optimization. Recent context can still enter
  through the context-dependent query projection (r = Sᵀq). A weak result does not exclude the shortcut interacting
  with other limits, such as the gate behaviour in diagnosis F3/F4.
- **Exploratory:** the artifact population 9_300_011+s was already evaluated for the P2.5 cells. No reserved
  population is used, so nothing here is a registered screen result.

## 3. Cells (2), one A100-80GB slot
| cell | config |
|---|---|
| `taskhead-learned-n32-s0` | P2.5 `base` with `readout = "taskhead"`, `n_bindings = 32`, `seed = 0` |
| `taskhead-learned-n32-s1` | same with `seed = 1` |

Everything else is byte-identical to the P2.5 grid `base`:
- arm learned, 4 queries, filler_len 40, 1,500 steps, batch 16, lr 3e-3
- eval_every 100, 4 eval batches, filler_len_schedule [[0,0],[1000,40]]
- backbone `qwen3-0.6b-base` (revision da87bfb6), cuda, FP32
- default P2.5 SGM: layers 6/13/20/27, 4 heads, d32, local 32+4, feature_shift 1, max_cells 2048
- filler_writes true, aux_address_lambda 0, no beta_bias_init

Group `p2p5-readout-probe-v1`. Two cells packed in one slot app, as in PK1.

Sameness checks (verified in code, `memsub/sgm/synthetic_pilot.py`):
- The training data stream is `Generator().manual_seed(seed)`, independent of the readout.
- Adapter initialization uses the same seed.
- Only the head differs: `Linear(512→64)` instead of `Linear(1024→64)`, drawn after `manual_seed(10_000+seed)`.
  This difference is unavoidable.

## 4. Populations
- dev 4242 (descriptive only)
- artifact 9_300_011+s: the final evaluation, all 5 interventions
- train-split 555_001+s
- The reserved 9_600_011+s is NOT touched. There is no readings run.

## 5. Comparator
The saved P2.5 residual-head rows `learned-n32-s{0,1}/…/out/per_example_results.jsonl`, sha-bound in the diagnosis json.
Pairing is by (batch, episode, episode_hash, query). If any hash differs, the contrast is `unavailable`. It is never
re-paired.

## 6. Frozen rules (existing code reused unchanged and bound by sha; no new thresholds)
- **Recipe contrast C.** Per seed s: `P2D.paired(T_s rows, R_s rows, "none", "none")` (episode-paired, 256 episodes).
  Then `P2G.classify({"0": …, "1": …})` gives one of: reproducible gain / reproducible loss / positive gain ≥5pp
  excluded / neither.
- **Bank dependence B.** `P2D.memory_use(T_s rows)["pass"]` on BOTH seeds. That requires bank_derange accuracy
  ≤ 0.04, and none−bank_derange and none−read_offset intervals with lo > 0.
- **Ordered reading:**
  1. A taskhead cell not COMPLETE and valid → `probe unavailable: <cell>: <state>`. There is no rerun, rescue or
     extension; any repeat needs a new user decision.
  2. C = reproducible gain and B → `taskhead recipe improves learned N32, with registered bank dependence (exploratory)`
  3. C = reproducible gain and not B → `taskhead recipe improves learned N32; registered bank dependence not established`
  4. Otherwise → `rescue by the taskhead recipe not shown (C = <label>)`
- **Descriptive only** (no decision role): dev curves, phase-1 versus phase-2 training accuracy, coord_shuffle /
  query_off, routing and gate telemetry, gradient None/zero counts.

## 7. Execution constraints (same discipline as the campaign)
- Exactly once per cell: at most 4 admitted starts with crash re-entry from acknowledged checkpoints (PK supervisor).
  An absolute deadline. Stop by bound id, verified with zero tasks and containers.
- chat_read immediately before any paid step. A pending codex audit blocks the launch.
- No campaign frozen bytes change: prereg, grid, registry, schema, manifest, runners and evidence.
- New files only. The large binaries (checkpoints, safetensors) are kept out of git and bound by SHA256SUMS.

## 8. Implementation plan (for the implementation audit)
1. Add a probe grid `configs/m4_sgm_p2p5_readout_probe_grid.json`, plus a probe registry and output schema derived the
   same way as the campaign's for the taskhead arm.
   - Under the task head, the last selected layer's `out_proj` / `alpha` receive no gradient, so their `grad_norm` /
     `update_norm` are absent (None), as documented in `_group_norms`.
   - The schema declares exactly the None leaves that a local smoke shows. Nothing is added after the fact.
2. Add a probe slot runner: a thin wrapper that reuses the frozen PK slot-runner logic through a PRIVATE import with
   rebound constants (grid, registry, schema, group, app, Dict names, price file).
   - Alternatively a minimal copy, if rebinding cannot work at Modal import time. The implementation decides and
     documents which.
   - Lifetime: one bound-id control-plane reaper, a new `-probe` registry and guard Dicts, and an absolute deadline
     from the ledger.
3. Add an analysis script `scripts/sgm-p2p5-readout-probe-reading.py`, local and CPU-only. It applies §6 to the
   fetched taskhead rows and the bound comparator rows, and writes write-once `probe-reading.json`.
4. Tests: rule application on fixtures, pairing refusal when hashes differ, None-leaf schema exactness, wrapper
   constant rebinding (with no campaign identifiers left), and mutation checks on private copies.
5. Smoke and parity:
   - local RTX 3060, ≤50 updates, $0: run the taskhead cell end to end, and confirm the data-stream sameness with the
     P2.5 learned-n32 config (identical episode hashes for the first batches)
   - CPU tiny-backbone bitwise default unchanged for residual_head
6. Price ledger with a cap request.

## 9. Cost (planning reference only; the cap is the user's)
- The actual P2.5 learned-n32 slot (2 packed cells, 1,500 updates each, ~5.9 h) billed **$20.10**. The taskhead
  backbone compute is the same; the head is smaller.
- Estimate ≈ $20 + image ≈ $0.2 + controller ≈ $0.1.
- Planned cap request: **$30**, which covers one crash re-entry. The final figure comes from the priced ledger in the
  implementation package.
- Alternative at $0: run the 2 cells on the local RTX 3060. It is much slower (roughly 1–2 days, not profiled) and runs
  on different hardware from the comparator. It is not recommended for the contrast.

## Unresolved questions
- Reuse the PK slot-runner logic via a private import, or a minimal copy? To be decided in implementation, with codex.
