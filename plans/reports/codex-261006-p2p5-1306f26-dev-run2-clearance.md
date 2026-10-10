# P2.5 development GPU run 2: limited technical clearance

The single six-case Qwen GPU numerical-parity run proposed in gravity 21490 is
cleared at commit `1306f2650e95bbbd8511c4afe274be359532fdf3` under the existing
option-A `$3` development authorization. This clearance checks losses, gradients,
initial/final trainable weights and dev predictions/accuracy. Training telemetry
and other dev numeric metrics remain outside the checker's verified contract.
The docstring's broader telemetry claim must not be used as an evidence claim.

## Independently checked source and behavior

- Candidate memsub:
  `b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085`.
- Frozen reference memsub:
  `048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.
- GPU runner:
  `e7b110ae0f3ce5cdae1470fc146d895cc1c4c035783bea3934b76ca2433df05f`.
- Parity checker:
  `b384c1037438dad91a51a4f05b41caf3c1563433a63fb0002a97104c3fb8c16d`.
- Hotspot script:
  `0c0524ac3bed5bb24ad53da89cd8a9c2eae30c9056f1d0427667a22745234476`.

Tracked implementation files match the frozen commit. Reference input hashing
agrees with the original profiled source. GPU parity still must bind the actually
executed candidate/reference hashes in its returned artifact.

The seven checker tests reject missing gradients/updates, non-finite gradients
and losses, changed tensor structure, parameter names/presence and nonidentical
initial weights. The no-gradient scatter ownership test passes; the gradient-path
test preserves gradients into all cells. These tests plus core/runtime, tiny
checkpoint-resume and artifact-hygiene checks independently pass: **43 tests in
33.17 s**. The historical stop file matches commit `2fda0d4` byte-for-byte, SHA
`40f6bac90ae5cde26e4c17cd2e9152e7553899d733f8d5517b77882eb1d7a559`; its
parsed sidecar and pinned hygiene exception preserve those original bytes.

The actual strict tiny CPU suite independently passes **11/11 bitwise**, with
zero reported problems and 33–99 compared tensor rows per case. Namespace
isolation passes. The deliberate delta perturbation fails (max relative
difference `0.6779181889985972`). This includes default-off resume additions in
the exact candidate tree. Three CPU checkpoint tests cover a tiny-backbone
interruption/resume fixture, foreign-config rejection and snapshot independence.
GPU resume and campaign-runner integration remain unverified. The author's
separate optimizer/generator mutation claims were not independently rerun here.

The actual revised runner passes six CPU-only substituted-result fixtures:
success, rc7, child timeout, remote exception, malformed archive and SIGTERM.
Failures propagate with saved manifests. Its SDK resource fields are hard
request/limit tuples: CPU `(4,4)` and memory `(32768,32768)` MiB. The manifest now
labels `$0.9582` as `function_only_charge_usd`, not an app/cumulative cost bound.

## Exact allowed GPU work

Use attached ephemeral `modal run` under `timeout --kill-after=15s 1200`, with the
reviewed runner and `scripts/sgm-p2p5-sgm-path-speedup-parity-check.py`, arguments
`--ref-tree dev-gpu-inputs/memsub-ref-2fda0d4 --suite qwen-gpu`, and a fresh
`dev-gpu/parity-qwen-gpu-v1` output directory. This permits one invocation only,
with no automatic retry, rescue precision change, detaching gradients, batch
reduction or test expansion.

All cases use Qwen3-0.6B-Base, CUDA, residual readout, N32, two training updates and
training-stream seed 99. The six cases are learned/b16 with training filler 0;
learned/b16 with filler 40; oracle, single_cell, random_fixed and memory_off/b4
with filler 40. The existing suite's dev evaluation uses seed 4242. Retain its
deliberate negative control and namespace isolation checks. No registered,
artifact or reserved test population is included. Checkpoint/resume options are
off. This is not a registered retiming or full campaign launch.

Keep the full run-1 `$1.55` reserve and run-2 `$1.18` reserve: **`$2.73` booked of
`$3`**, leaving `$0.27` unallocated. The run-2 calculation uses 1200 seconds of
client lifetime plus 120 seconds of termination/disconnect allowance, 2x nominal
CPU/RAM for conservatism despite hard tuples, `$0.03` for cached build overhead
and `$0.10` margin. It rounds `$1.1713216` upward to `$1.18`. The 120-second
allowance includes the 15-second kill escalation; it is an assumption, not a
platform guarantee. Build caching must be checked at launch; unexpected build
cost needs reconciliation within the existing cap before more paid work. No
reserve is released from the run-1 billing snapshot alone.

Accept GPU parity only with complete six-case artifacts, matching candidate and
reference hashes, every checked tensor comparison passing at rtol `1e-5`,
identical dev predictions/accuracy, detected negative control, successful
isolation, and successful child exit. Verify app shutdown independently using
stopped state, zero tasks and zero matching containers; retain failure artifacts
if the attached client times out or a case fails. CPU fixtures do not establish
real remote shutdown or build-failure/host-loss reporting.

## Remaining claim limits

Actual counterexamples show `compare()` accepts a NaN dev loss, and reports
PASS plus `bitwise=True` with NaN training telemetry. Thus `bitwise` is a statement
about checked tensors and selected dev float fields; it is not full output or
telemetry equivalence. Do not use this suite to clear telemetry, scientific
metrics, GPU resume, all-arm campaign equivalence, registered timing or learning
claims. The GPU artifact is required before any GPU numerical-parity conclusion.

## Evidence

- `codex-261006-p2p5-1306f26-tests.log`
- `codex-261006-p2p5-1306f26-tiny-parity/parity.json` and corresponding `.log`
- `codex-261006-p2p5-1306f26-source-and-scope-check.json`
- `codex-261006-p2p5-1306f26-runner-failure-check.json`, produced with the existing
  `codex-261006-p2p5-dev-v2-failure-check.py` helper and a new output path

This audit makes no implementation edit, paid launch, commit, push or deployment.
