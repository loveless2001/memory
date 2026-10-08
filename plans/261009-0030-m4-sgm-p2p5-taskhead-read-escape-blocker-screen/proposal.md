# P2.5 taskhead read-escape blocker screen (Stage A), proposal v0.4 (EXPLORATORY)

## History and approval
- Reviews: v0.1 41ffbd2 (codex 21975), v0.2 4ee2a52 (codex HOLD 21987), v0.3 111901c (codex HOLD 21999). v0.4 applies 21999.
- User 21977: "Check fix then modal run", meaning Modal at the $4 cap. Codex confirmed no new approval is needed while scope and cap stay fixed.
- Launch requires codex's re-check of this package.

## Why
Diagnosis fa0e44d (descriptive): taskhead reads overlapped the writes at the reconstructed init. **By update 100** they had separated by about 10 cells. Pooled absent weight was 99.3% (s0) and 99.1% (s1); not every read became absent. The separation persists at 1500. H1 and H2 are untested, and neither larger models nor more training was tested as a remedy.

## Question
Does an intervention keep taskhead reads on the memory through the first 100 updates, where the unchanged recipe loses them?

This is an operational routing-retention screen, not a learning or capability condition. The working toy also stays near ln 64 and chance accuracy through phase 1, so loss and accuracy are descriptive only.

## Arms
All arms use the probe recipe, bound by the sha256 4e89b95a… of the probe s0 run_manifest (copy in `inputs/`). The base must equal:
- frozen Qwen3-0.6B-Base; learned addresses; taskhead; N32; batch 16;
- curriculum ((0,0),(1000,40)), so all 100 updates are phase 1;
- seed 0 (the probe's init and train stream); lr 3e-3; aux 0;
- FP32 with TF32 off (pinned builder).
Batch 2 is refused.

| arm | change | label |
|---|---|---|
| A0 | none | within-setting gate. Runs FIRST; if it is INVALID or not `escaped` at 100, stop before A1/A2 |
| A1 | lr 3e-4 for ALL trainable parameters | global-rate intervention. Not an isolated address-lr test or a causal H2 test |
| A2 | `aux_address_lambda` 0.1 | PRIVILEGED training correspondence supervision (binding positions; AddressMLP-only via detached q/k). A constant address map gives zero aux loss, so a kept A2 shows neither useful discrimination nor an unsupervised remedy. The manifest has `stage_a.supervision`; the logged loss is task+aux |

Max 3 × 100 = 300 updates. Fresh state per arm; one start per arm; no retries or fallback.

## Readouts (frozen)
- **Dev evals** at updates 0/25/50/75/100 via `train()`'s `evaluate_fn`, dev-only: heldout split, seed 4242, 4×16 episodes × 4 queries, filler 40. No run_pilot final, intervention or train-split evals.
- **Endpoint:** pooled `query_empty_read_weight` over all layers and heads.
  - **escaped:** ≥ .9
  - **kept:** ≤ .2
  - **partial:** between
  - These are operational bands.
- **INVALID:** at any sampled step, a value that is missing, duplicate, boolean, non-finite or outside [0, 1].
- `band_at_100` and `kept_through_100` (≤ .2 at every sampled point) are reported separately.
- **Geometry afterwards (local, $0):** the cleared diagnosis script runs on a new bound three-entry index (final = step 100). It reports per-head absent weight, exact all-absent fractions, offsets, alignment, q cosines, collisions and effective cells. The index and argv go to codex first.
- **Descriptive:** train loss, address-MLP gradient norms, dev accuracy.

## Execution
- **Script:** `scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py` runs one arm. It reuses `train`, `evaluate` and `save_trained_parameters`; memsub is unchanged.
- **Runner:** `modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py`, ONE ephemeral `modal run`.
  - **Image:** `Image.from_id("im-A7BXMB8v1cVYRvC9pMqZ3i")`, the dev-GPU runner's pinned torch 2.7.1+cu126 / transformers 4.55.2 / Qwen weights image (hotspot-l40s-v1.console.log:142–155). No image is constructed. The repo files are runtime mounts. Modal can't look an image up offline (`base-image-lookup-attempt.txt`). A missing id fails at app startup before any GPU container.
  - **Resources:** L40S, CPU (4,4), RAM (32,32) GiB; retries 0; max_containers 1; scaledown_window 2; startup_timeout 300; function timeout 1560.
  - **Campaign deadline:** the local entrypoint writes ONE immutable deadline (first call + 4500 s) to Dict `m4-sgm-p2p5-stage-a-read-escape-starts-v2`. A used Dict refuses a relaunch.
  - **Remote function, in order:**
    1. Refuse if ≤ 90 s remain at entry.
    2. ARM the whole-worker deadline killer: an own-session sleeper that SIGKILLs this worker at the absolute deadline. It is armed before any blocking setup and cancelled in finally.
    3. Atomic `Dict.put(arm, …, skip_if_exists=True)`; a second start refuses.
    4. The Dict's deadline must equal the one passed.
    5. Pinned version check.
    6. **Re-read the remaining time immediately before the child**; < 600 s refuses.
    7. Run the child in its own session, with timeout min(1500, remaining − 90) and its own absolute group killer (`kill -KILL -<pgid>`, dash syntax verified locally).
    8. Return the tar of a fresh per-call `mkdtemp` directory.
  - **Local sequence:** A0 → gate → A1 → A2. Each tar is extracted before the next call; the first error, refusal or INVALID stops.
- **After the client:** `<runner> cleanup-verify <out>` stops the recorded app id with a bounded CLI call. It then requires the reused PK `verify_stopped` (app stopped, zero tasks, zero containers), with up to 4 checks 20 s apart for lagging task counts. It writes cleanup.json. A missing run.json gives `unresolved`.
- **Charge reservation** (`ledger()`): (client lifetime 4740 s + app-stop allowance 300 s) × ($0.000542 L40S + 1.25 × 4 × $0.0000131 CPU with an overuse margin + 32 × $0.00000222 RAM) = **$3.4 ≤ $4**.
  - **Enforced server-side:** no arm work runs past the deadline. After it, only entry refusals and startups (≤ 300 s) can occur, until the client exits.
  - **Unenforced:** the app-stop latency after the client exits. cleanup-verify checks it.
  - So this is a reservation, not a proven worst case.
  - **Expected:** about $2.5 (≈19 min per arm, extrapolated from the L40S residual-head profile and the probe's A100 timing; not taskhead or A2 proof).
- **Launch:** ONCE, via `setsid nohup bash plans/261009-0030-…/launch-stage-a-once.sh`. It refuses on a dirty tracked tree or an existing out dir. It records HEAD, pid/pgid/sid, the argv (`timeout --signal=TERM --kill-after=30s 4710 .venv/bin/python -m modal run <runner> --out <P>/stage-a-run-v1`), the console, both exit statuses and the cleanup verdict.

## Evidence (CPU, $0)
- `focused-tests.txt`: all passed, EXIT 0. Covers:
  - bands and INVALID cases, including booleans and out-of-range values;
  - the recipe binding;
  - tiny end-to-end A0/A1/A2;
  - A0→A1→A2 in one warm worker with isolated tars;
  - restart refusal;
  - the immutable deadline and relaunch refusal;
  - codex's fake-clock reproducer (setup consumes the deadline, so the child is refused);
  - the entry refusal arming nothing;
  - worker and child-group guards armed with absolute times;
  - a real process-group kill, and cancel preventing it;
  - cleanup strict / retry / no-id / no-run.json;
  - reservation ≤ cap.
- `mutation-checks.json`: 21/21 private-copy mutants caught, EXIT 0.

## Decision use
- If an arm is **kept** while A0 is **escaped**, propose Stage B (that arm, 1500 updates, 2 seeds). Stage B needs its own proposal, cap and user go.
- Otherwise, report and stop. The write-up stays open.

## Not in scope
No 4B, no reserved seeds, no change to registered readings, and no claim beyond the descriptive Stage-A readouts.
