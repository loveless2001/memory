# P2.5 readout-recipe rescue probe: frozen proposal v0.2 (EXPLORATORY)

v0.2 applies codex 21750 (`plans/reports/codex-261008-p2p5-pk-21749-proposal-audit/`): §8.1 None-vs-zero
contract, §8.2 a path-aware validator wired into COMPLETE/collect/reading, §8.3 new runner entry points, §7 bounded
recovery, §8.5 bounded smoke, §9 full-envelope pricing, and the "reused bank-dependence criterion" label. The
scientific scope is unchanged.

Status: design PASS for local implementation (codex 21750). User 21748 asked for this proposal ("write the probe then"). This document does NOT
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
  the taskhead model meets the REUSED bank-dependence criterion (P2D `memory_use`).
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
  2. C = reproducible gain and B → `taskhead recipe improves learned N32; the reused bank-dependence criterion is met (exploratory)`
  3. C = reproducible gain and not B → `taskhead recipe improves learned N32; the reused bank-dependence criterion is not met (exploratory)`
  4. Otherwise → `rescue by the taskhead recipe not shown (C = <label>)`
- **Descriptive only** (no decision role): dev curves, phase-1 versus phase-2 training accuracy, coord_shuffle /
  query_off, routing and gate telemetry, gradient None/zero counts.

## 7. Execution constraints (same discipline as the campaign)
- **Exactly once per LOGICAL cell.** The inherited PK supervisor gives at most 4 admitted starts, and each start
  re-enters from that cell's last acknowledged generation (C = 50 updates, so a lost start loses at most C+1 = 51
  updates).
  - A start lost BEFORE a cell's first acknowledged generation replays that cell from scratch. This bounded
    pre-checkpoint replay is ALLOWED and declared in the record, exactly as in the campaign.
  - No logical FAILED/COMPLETE state is reset or relabelled, and there is no training extension.
  - A cell that is not COMPLETE and valid when the slot ends makes the probe `unavailable`.
- **ONE immutable whole-slot deadline** is written once at spawn: the v6 learned-n32 slot reserve life, 31,946.2 s
  (same workload, different head). An in-process SIGKILL watchdog fires at that deadline, starts are refused past
  it, and the in-app reaper stops the app by its bound id. Collect stops and verifies the app by its bound id (zero
  tasks and containers).
- chat_read immediately before any paid step. A pending codex audit blocks the launch.
- No campaign frozen bytes change: prereg, grid, registry, schema, manifest, runners and evidence.
- New files only. The large binaries (checkpoints, safetensors) are kept out of git and bound by SHA256SUMS.

## 8. Implementation plan (for the implementation audit)
1. Add a probe grid `configs/m4_sgm_p2p5_readout_probe_grid.json`, plus a probe registry and a PATH-EXACT output
   schema. Both are derived by a freeze script from the frozen campaign learned registry and schema, with every
   `L{L}` key expanded to the exact selected layers. Only the following change:
   - registry: the head becomes `Linear(512→64)`. Every adapter parameter stays, including the disconnected ones.
   - **None-vs-zero contract** (derived from the graph, codex 21750 #1). Only `grad_norm` leaves can be None;
     `update_norm` is a parameter-difference norm and is ALWAYS numeric (0.0 for an unchanged parameter).
     a. REQUIRED null: `grad_norm` `L27/out_proj` and `L27/alpha` on every logged row and in `train_last`. These
        parameters only feed layers after the last selected layer, which the task head never reads.
     b. Number-OR-null: `grad_norm` `L{l}/k_proj`, `L{l}/value`, `L{l}/beta` for every selected layer l. These
        write-path parameters reach the loss only through a read (at ingest or query time) of a cell written in
        that batch's graph; a batch where no read in layer l touches such a cell leaves them None (`_group_norms`: no gradient
        reached the group). This is the class seen in learned-n32-s1 L20.
     c. Everything else is numeric, as in the campaign schema: q_proj, address_mlp, out_proj/alpha below L27,
        head, and all of update_norm.
   - These paths are fixed in code BEFORE any model smoke. They are verified on the tiny CPU backbone by tests:
     (a) appears on every logged row; a forced read-miss produces (b) while q_proj/address_mlp stay numeric; and a
     residual-head control produces neither (a) nor the expansion. The bounded Qwen smoke then checks (a)/(c)
     only. No allowance is ever added after results are observed.
2. **Probe validator** `scripts/sgm-p2p5-readout-probe-output-validation.py`:
   - It runs the ORIGINAL `validate_cell_outputs` with schema=None. That keeps every other check: done.json hashes,
     strict finite JSON, manifest/populations, row coverage and episode hashes, metric/row agreement, telemetry
     counts and steps, the registry and finiteness, and wall_seconds.
   - It then applies the path-exact schema with the contract above to metrics.json and to EVERY telemetry row
     (not only the first row of each kind).
   - It is wired into the supervisor's COMPLETE transition through a `ProbeSlotSupervisor` subclass, a narrowly
     copied `finish`. Collection and reading use the same validator. memsub and the campaign files are unchanged.
3. **New probe runner entry point** `modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py`. It does NOT
   import or rebind the decorated campaign module. Probe constants are set before any Modal object is built:
   - app `memsub-m4-sgm-p2p5-readout-probe`, with its own guard/admission Dicts
   - volume subpath `m4-sgm/p2p5-readout-probe-v1/`
   - the image mounts memsub, configs, the validator and the shared lifetime-stop logic
   Pure lifecycle code (admission, provenance, cell report, collect orchestration) lives in a separate logic
   module, so it can be tested without Modal. Lifetime is handled by an IN-APP scheduled reaper (CPU, every 120 s)
   using the shared `modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py` `reap_and_stop` / `stop_bound_app`, the path
   proven by the P2.5 self-stop proof. There is no campaign controller, no readings horizon and no campaign
   manifest. Tests check the actual bound app, image mounts, decorator resources, Dict names, volume subpath,
   deadline and collect targets, and that no campaign writable identifier remains.
4. Add an analysis script `scripts/sgm-p2p5-readout-probe-reading.py`, local and CPU-only. It applies §6 to the
   fetched taskhead rows and the bound comparator rows, and writes write-once `probe-reading.json`.
5. **Tests (CPU, tiny backbone):**
   - grid → exactly 2 cells, equal to the P2.5 base except the readout
   - the training data stream is identical across readouts (pure data generator)
   - the contract tests from §8.1
   - the campaign validator rejects a taskhead run while the probe validator accepts it
   - schema-contract unit cases
   - the subclass COMPLETE path uses the probe validator
   - reading rules on fixtures, including hash-mismatch refusal and the FAILED/LOST → unavailable path
   - runner binding checks
   - collect with injected fakes
   - mutation checks on private copies
   The frozen implementation goes to codex BEFORE any model smoke.
6. **Bounded local Qwen smoke** (RTX 3060, $0; only after the implementation review). One taskhead cell config
   with ≤ 50 updates, under an OUTER whole-process wall deadline of 3,600 s that covers load, evaluation and
   cleanup. Partial evidence is kept and there is no automatic retry. It uses its own namespace
   (`…/readout-probe-smoke/`) and its own populations: train seed 7, dev 777_001, final 777_100+s, train-split
   777_200+s. It never uses the probe cells or their populations.
7. **Price ledger** `scripts/sgm-p2p5-readout-probe-priced-ledger.py`, which prices the full envelope (§9).

## 9. Cost (planning reference only; the cap is the user's)
- **Expected:** the actual P2.5 learned-n32 slot (2 packed cells, ~5.9 h wall) billed **$20.10**. The taskhead
  backbone compute is about the same.
- **Full envelope (the cap request):** the whole immutable deadline at the v6 worst-case billing basis.
  (31,946.2 s + 240 s stop tail) × rate(2.0) = $0.00118776/s, about $38.2. Plus the image ($0.17), the in-app reaper
  ticks (about $0.2) and a $2 margin: about **$41**. The exact figure comes from the ledger script. The draft $30 did
  not cover the full 4-start envelope.
- Alternative at $0: run the 2 cells on the local RTX 3060. It is much slower (roughly 1–2 days, not profiled) and runs
  on different hardware from the comparator. It is not recommended for the contrast.

## Unresolved questions
- Reuse the PK slot-runner logic via a private import, or a minimal copy? To be decided in implementation, with codex.
