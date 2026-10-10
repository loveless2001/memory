# P2.5 taskhead read-escape blocker screen (Stage A), proposal v0.3 (EXPLORATORY)

## v0.3 delta (codex 21987 HOLD fixes; arms, readouts and scope unchanged)
1. **Warm container.** Each remote call writes to a fresh `tempfile.mkdtemp` directory. The test runs A0 → A1 → A2 in ONE reused raw worker, with each tar holding only its own arm. The second-start refusal is kept.
2. **Cost bound.**
   - **Image:** `Image.from_id("im-A7BXMB8v1cVYRvC9pMqZ3i")`, the dev-GPU runner's pinned torch 2.7.1+cu126 / transformers 4.55.2 / Qwen weights image (built in hotspot-l40s-v1.console.log:142–155, reused from cache afterwards). There is no image build, so the build cost is $0. Modal can't look an image up offline (`base-image-lookup-attempt.txt`). A missing image fails at app startup before any GPU container. Inside the container, the versions and the pinned model-file shas are checked before any training.
   - **ONE immutable campaign deadline:** first-call time + 4500 s, written once to `m4-sgm-p2p5-stage-a-read-escape-starts-v2` (a used Dict refuses a relaunch). Each call refuses unless its deadline equals the Dict's and at least 600 s remain. Child timeout = min(1500, remaining − 90).
   - **Teardown:** scaledown_window=2. max_containers=1, so containers never overlap.
   - **Ledger:** GPU-container seconds ≤ client lifetime (4740 s) + app-stop allowance 300 s, at $0.00066544/s = **$3.354 ≤ $4**. The stop allowance is the only unenforced term. ~970 s more would still fit under the cap.
3. **classify** rejects booleans and values outside [0, 1] at any sampled step. Boundary and refusal tests are added.

The v0.2 sections below remain valid, except: the image is from_id, the deadline is the campaign deadline, and the launch argv uses timeout 4710 (OUTER 4740 − 30 kill-after).

- v0.1 41ffbd2 was reviewed by codex in 21975 (`plans/reports/codex-261009-p2p5-pk-21973-stage-a-proposal-review/`). v0.2 applies all six points.
- User 21977: "Check fix then modal run". That is Modal venue (a) at the $4 cap proposed in 21973.
- Launch still requires codex re-review of the concrete wrapper, index and argv below.

## Why
Diagnosis fa0e44d (descriptive): taskhead reads overlapped the writes at the reconstructed init. **By update 100** they had separated by about 10 cells, with pooled absent weight 99.3% (s0) and 99.1% (s1); the separation persists at 1500. Not every read became absent. H1 and H2 are untested, and neither larger models nor more training was tested as a remedy.

## Question
Does an intervention keep taskhead reads on the memory through the first 100 updates, where the unchanged recipe loses them?

This is an operational routing-retention screen. It is **not** a necessary or sufficient learning condition. The working toy (P2C) also stays near ln 64 and chance dev accuracy through phase 1, so loss and accuracy are descriptive only.

## Arms
All arms use the probe recipe, bound by the sha256 of the probe s0 run_manifest (copy in `inputs/`):
- frozen Qwen3-0.6B-Base; learned addresses; taskhead; N32; batch 16;
- curriculum ((0,0),(1000,40)), so all 100 updates are phase 1;
- seed 0, so the init and train stream are the probe's;
- FP32 with TF32 off (pinned builder).

| arm | change | label |
|---|---|---|
| A0 | none | within-setting gate. Runs FIRST. If it is INVALID or not `escaped` at 100, stop before A1/A2 and report the non-replication |
| A1 | lr 3e-3 → 3e-4 for ALL trainable parameters | global-rate intervention. Not an isolated address-lr test and not a causal H2 test |
| A2 | `aux_address_lambda` 0.1 | PRIVILEGED training correspondence supervision (binding positions; AddressMLP-only via detached q/k). A constant address map gives zero aux loss (codex verified), so a kept A2 does not establish useful discrimination or an unsupervised remedy. Report collisions, effective cells and geometry. The logged loss is task+aux combined. The manifest carries explicit supervision metadata |

No arm replacements or expansion. Max 3 × 100 = 300 updates.

## Readouts (frozen)
- **Dev evals** at updates 0/25/50/75/100 via `train()`'s `evaluate_fn`, dev-only: heldout split, seed 4242, 4×16 episodes × 4 queries, eval filler 40. There are no run_pilot final, intervention or train-split evaluations.
- **Endpoint:** pooled mean query absent-read weight over all layers and heads (`query_empty_read_weight`).
  - **escaped:** ≥ .9
  - **kept:** ≤ .2
  - **partial:** between
  - These are operational bands, not learning or capability conditions.
- **INVALID:** a missing, duplicate or non-finite endpoint at any sampled step.
- **"kept at 100" ≠ "kept through 100".** "Kept through 100" requires ≤ .2 at every sampled point.
- **Geometry after training (local, $0).** The cleared diagnosis script runs on a NEW three-entry bound index, built from the fetched outputs (kind geometry, final = step 100). It reports per-head absent weight, exact all-absent fractions, offsets, alignment, q cosines, collisions and effective cells. The index builder and argv go to codex before that local run.
- **Descriptive:** train loss (task+aux for A2), address-MLP gradient norms every 10 updates, dev accuracy.

## Execution (Modal; concrete)
- **Script:** `scripts/sgm-p2p5-taskhead-read-escape-stage-a-train.py` runs ONE arm and writes run_manifest.json, routing_telemetry.jsonl, trained_parameters.safetensors and stage_a_result.json. It reuses `train`, `evaluate` and `save_trained_parameters` unchanged. memsub is unchanged.
- **Runner:** `modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py`.
  - ONE ephemeral `modal run`.
  - **Hardware:** L40S, CPU (4,4), RAM (32,32) GiB hard tuples; retries 0; max_containers 1. The image is the pinned stack copied from the dev-GPU runner.
  - **Per-arm whole-worker deadline:** Modal function timeout 1560 s; child subprocess timeout 1500 s. Partial telemetry is flushed and returned.
  - **Restart accounting:** the first statement is an atomic `Dict.put(arm, …, skip_if_exists=True)` on `m4-sgm-p2p5-stage-a-read-escape-starts-v1`. A second start of an arm refuses before any model work.
  - **Sequence:** the local entrypoint runs A0 → gate → A1 → A2. Each arm's tar is extracted before the next. The first error, refusal, timeout or INVALID stops the sequence. There are no retries or fallback.
- **Ledger** (all-in upper bound, `ledger()`): about $3.72 ≤ the $4 cap.
  - Rate: $0.00066544/s = L40S $0.000542 + 4 × $0.0000131 + 32 × $0.00000222.
  - Client lifetime 5100 s ($3.394), worst-case image build ($0.084), 3 × 120 s teardown ($0.240).
  - **Expected about $2.5:** roughly 19 min per arm, extrapolated from the 9.44 s/update L40S profile (residual head) and the probe's ~10 s/update on A100. This is not taskhead or A2 proof.
- **Launch.** Run ONCE, detached with setsid. The console and exit status are recorded beside the output, outside the out dir:
  `timeout --signal=TERM --kill-after=30s 4710 .venv/bin/python -m modal run modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py --out plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/stage-a-run-v1`
- **Afterwards:** app-filtered billing; geometry index and local diagnosis; result post to codex.

## Evidence (CPU, $0)
- `focused-tests.txt`: 15 passed, EXIT 0. Covers:
  - bands and INVALID cases;
  - the probe-manifest binding and arm configs; batch 2 is refused;
  - tiny end-to-end A0/A1/A2, with A2's aux loss finite and logged;
  - the runner gate, including A0 non-escape stopping;
  - the second-start refusal before any child;
  - ledger ≤ $4.
- `mutation-checks.json`: 6/6 private-copy mutants caught, EXIT 0.

## Decision use
- If an arm is **kept** while A0 is **escaped**, propose Stage B (that arm, 1500 updates, 2 seeds). Stage B needs its own proposal, cap and user go.
- Otherwise, report and stop. The write-up stays open.

## Not in scope
No 4B, no reserved seeds, no change to registered readings, and no claim beyond the descriptive Stage-A readouts.
