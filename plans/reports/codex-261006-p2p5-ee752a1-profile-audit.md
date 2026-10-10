# P2.5 implementation checkpoint and retained OOM audit

Reviewed `ee752a1064aff1ccbb87580bf4d3728ff517326e` on 2026-10-06 in response to
#gravity 21436. This review preserves the stopped local attempt and clears no
new GPU execution. **The first configuration did not complete; throughput,
fit on a larger GPU, and the charged training ledger remain unmeasured. The
hard outer deadline is still unresolved in the committed runner.**

The reproducible checks are `codex-261006-p2p5-ee752a1-profile-checks.py` and
its adjacent JSON. They use the CPU environment and a substituted sleep for
the deadline probe; they perform no training, model evaluation, CUDA work,
or reserved-population access. The separate existing CPU tests below were
run once for this review.

## Verified evidence

- `profile.json` matches the current memsub source hash
  `048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.
  It records `stopped: OOM at learned phase 1`, 49.4413 seconds, and an empty
  completed-config list. Its first-error branch stops the loop. No throughput
  or accuracy appears in the saved output.
- The saved CPU/CUDA tolerance results report PASS for tiny and pretrained
  paths. The saved differences are within the stated tolerance. These are
  checked retained results, not an independent CUDA rerun.
- Independent CPU tests at the reviewed source: pretrained residual/readout
  path **7 passed in 48.48s**, exit 0; legacy default-build/default-trainer
  fingerprints **4 passed in 32.02s**, exit 0. Commands:

  ```sh
  .venv/bin/python -m pytest -q tests/test_sgm_p2p5_pretrained_qwen_residual_readout_path.py
  .venv/bin/python -m pytest -q tests/test_sgm_p2g_gate_knob_and_decision_rules.py tests/test_sgm_p2c_filler_length_curriculum.py -k 'default_build_is_bitwise or empty_schedule_is_bitwise'
  ```

- The current CPU environment remains torch `2.7.1+cpu`, transformers
  `4.55.2`, safetensors `0.5.3`. The retained full-suite file reports 213
  passed, exit 0, against `7ff926f` plus then-uncommitted changes. That record
  is not an independent full-suite rerun or an exact committed-source binding.
- Grid arithmetic reproduces the 18 registered cells and the fixed schedule
  and population identifiers. The implementation's ordered reading table
  passes 1,024 flag/label combinations across both loads; four malformed
  interface inputs are rejected. The private observer registers exactly the
  intended 16 heads. This does not certify its complete readings/launch flow.
- Source inspection confirms final normalized query residual readout, the
  trained local-only head branch, frozen backbone, and opt-in CUDA completion
  synchronization after the optimizer step. Default CPU fingerprints agree.

## Remaining deadline hold

The script checks the 1,800-second limit only before `profile_config()`.
Loading, a full update, evaluation, and cache cleanup can continue beyond it;
the final report is written only after the loop returns. A CPU-only probe
replaced the workload with a 150ms sleep and the bound with 10ms: a complete
configuration was accepted after the deadline, then the loop stopped at
151.3ms. The committed script therefore provides a cooperative limit.

The actual retained OOM stopped well inside 30 minutes. This finding does
not assert that this attempt exceeded the limit. #gravity 21438 requests
any external supervisor command and its exit/termination evidence; none
is present in the retained profile log at review time. Before a future
profile, bind the supervisor, retain progress and failure stage atomically,
and prove that it terminates the whole worker at the deadline. Do not rerun
the laptop attempt to supply missing evidence.

## Claim and cost corrections

The artifact does not retain update counters or a forward/backward/evaluation
failure stage, so it cannot independently establish the reported "update 0".
The error text reports allocations exceeding the nominal 6GB device and an
impossible total process-memory value. Preserve that diagnostic verbatim;
it does not establish physical peak memory, WSL spill behavior, or the
unmeasured 15–25GB phase-2 fit estimate.

If every one of the 27,000 updates took the hypothetical 3–6 seconds, training
alone would take **22.5–45 GPU-hours**. At the current L40S base rate of
$0.000542/s, that is **$43.90–87.80 GPU-only**, or **$131.71–263.41** at the
listed 3x non-preemptible rate. CPU/RAM, both-phase weighting, arm/load proxy
assumptions, evaluation, startup/builds, shutdown, and margin remain to be
priced. These are arithmetic scenarios, not measured estimates. Rates and
the non-preemptible multiplier were checked against [Modal pricing](https://modal.com/pricing).

## Authorized boundary and next action

The prereg Gates 2–3 require separate explicit approval for a paid Modal
profile and an audited implementation plus fresh cap approval for registered
cells. The proposed $3 L40S profile is not a cleared runner or a priced ledger.
A concrete profile runner must preserve the four-config, 40-update protocol,
stop on the first OOM/error/preemption without replay, enforce one total
deadline, account for all charges, bind inputs/environment, retain progress,
and verify shutdown. It can then be audited before the paid decision.

No CUDA profile, registered cell, artifact/reserved evaluation, deployment,
retry, remote write, or push was performed by this review. The OOM artifacts
and all implementation sources are unchanged.
