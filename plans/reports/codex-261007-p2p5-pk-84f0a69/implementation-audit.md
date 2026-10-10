# Independent implementation audit: Amendment PK at 84f0a69

Reviewed 2026-10-07 Asia/Bangkok. **Not cleared for a GPU-proof approval request.** Free implementation and CPU
preparation remain authorized. The implementation has useful working foundations, but the proof acceptance,
completion validation, timing payload and charged lifecycle need the corrections below before paid work.

The original preregistration/grid/amendment hashes and historical profile/ledger inputs are preserved. Working
source bytes match the named commit. Memsub source is
`e330e309148f8ac856072c27d81d7da3b45db3a73374bedfafa8498024ee5ab9`;
runner `8f9e374c4b2c5f62e908095fc288320cab3c7f2a6be2b993b74fdb320823b94b`;
proof grid `4e32a3ef1e4cc6eef10deaac2972d857a2c7f42432e76cf4e7a959aada2e54da`;
timing `df48522d02279cf521923531d6818536c0626878caa844cb20f750bc461433ee`;
comparator `8748cce995ee3a40d058078815185bebd3ad5cf12597d341bd20c663e5e559c4`.
The packing/reaper helpers retain their previously reviewed hashes. Bindings and checks are in
`audit-bindings-and-checks.json` beside this report.

## Independently verified positive evidence

- The six focused test files (epoch state, real-worker supervisor, proof comparator, proof runner, checkpoint
  resume and audited packing measurement) pass: **52 tests in 198.30 seconds, exit 0**. The subprocess evidence
  is retained in `pytest-tmp/`; commands/status and output are retained separately.
- Independently reconstructed the profiled reference's memsub from git `2fda0d4`, then reran the existing tiny
  CPU parity suite against the current source: **11/11 bitwise**, negative control detected, import isolation
  passed. Reference source hash is `048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.
  This is the checker's existing tiny scope, not all numerics or a GPU/campaign result.
- Reviewed the committed `359 passed in 446.15s` suite log and the 18/18 tiny CPU timing smoke. The full 359
  tests and the entire timing smoke were not independently rerun; the independently executed subset is the
  52-test set above. No broad-suite rerun is needed to establish the concrete blockers below.

## 1. Charge every lifecycle path; keep spending claims assumption-bound

The runner prices nine *admitted* slot starts and one timing start with 120 seconds of startup, while both GPU
functions permit `startup_timeout=300` (runner lines 130, 172, 213–233). Using 300 instead of 120 alone changes
the arithmetic from **$9.192976275 to $11.330944275**, before any rejected starts, crash loops, idle teardown or
other omitted lifecycle work.

Admission bounds training work after admission; it cannot bound a crash occurring before the admission RPC.
Modal documents a separate container-crash path that retries indefinitely for deployed apps. Execution timeouts
are per attempt and are separate from configured startup time. These platform facts were checked in the current
[failures/retries documentation](https://modal.com/docs/guide/retries) and
[timeout documentation](https://modal.com/docs/guide/timeouts). `single_use_containers` and ordinary exception
retry count do not establish a finite pre-admission start count.

At the existing rate assumption, seven GPU containers for 4200+120+120 seconds cost **$36.9155808**;
adding the existing reaper/image/margin parts gives **$37.342888275**. This is lifetime-allowance arithmetic,
not a platform-guaranteed maximum. The 2x CPU/RAM basis, scheduled-reaper delay, stop latency, teardown and build
allowances remain assumptions. Resource rates were checked against [Modal pricing](https://modal.com/pricing).

The proposed serial redesign in message 21565 is a reasonable direction: one decorated GPU function shared by
all seven proof units, `max_containers=1`, with single-use containers and the same bounded logical admission.
Verify that no separate timing/slot function can allocate another GPU, and account for rejected starts, startup,
idle/termination work, reaper, image and margin over the whole lifecycle. Explicitly bind and test the new
deadline/stop plan. At a hypothetical 6600-second lifetime, the GPU allowance alone is $8.1242784; this does not
clear a new $8.6 reservation. Do not call either an estimate or this allowance a guaranteed maximum. Message
21566 still uses a stronger guarantee than the evidence supports. No automatic paid retry or scope reduction.

## 2. The acceptance checker compares peers without enforcing the frozen complete schema

The expected gradient list comes from A's first capture (comparator lines 151–165), not an independently frozen
name/shape registry. Metrics, telemetry, rows and final tensors are compared between runs without requiring their
expected contents/counts. The following production `evaluate()` outcomes were reproduced on fresh copies of the
independently generated real-worker CPU proof:

| Mutation to copied evidence | Actual result | Required result |
| --- | --- | --- |
| Remove one expected gradient name from every capture | PASS | FAIL |
| Empty every completed run's metrics, telemetry, per-example rows and final tensor set, then rebind its output hashes | PASS | FAIL |
| Remove every checkpoint-generation file | PASS | FAIL |
| Change inherited predecessor-record hashes to all zeros | PASS | FAIL |
| Change every record's source identity and make all epochs claim the same container | PASS | FAIL for invalid identity; fresh-container provenance must also be checked in GPU mode |

The original CPU proof remains untouched. Reproductions and results are retained in
`independent-rejection-probes.py`, `independent-rejection-probes-run2.json/.txt` and `rejection-probes-run2/`.
These are validator counterexamples, not observed GPU failures or claims that the actual good CPU outputs were
incorrect. The original deliberate-gradient-error and unstable-control tests continue to pass.

Freeze the expected trainable gradient names/shapes and final state names/shapes independently of A's emitted
gradients. Validate each run against the schema before comparing pairs: full metrics structure, N/A rules,
training/dev logical records, exact populations/interventions/episode-row counts, complete tensors, clocks and
deadline checks. Reject joint omissions as well as asymmetric defects. At the actual proof batch size, a learned
cell has 5 interventions x 1 batch x 16 episodes x 4 queries = **320 heldout per-example rows**; train-split
evaluation contributes the separately declared two batches and is not written into this heldout row file.

## 3. Validate durable completion and bind the retained consumer artifacts

The actual supervisor's `finish()` accepts `done.json={"outputs":{}}` and publishes COMPLETE without any output
files (lines 137–148). An independent direct probe reproduced that transition. Matching a worker-supplied list
of hashes does not establish the preregistered per-cell schema. Validate the mandatory file set, configs, source/
model/seed bindings, tensor completeness and finite metrics/rows before COMPLETE. Follow PK2's two-stage order:
commit validated outputs first, then publish and commit COMPLETE. Currently there is only the pointer publication's
single commit for both. Add CPU failures at both commit boundaries; no worker acknowledgement may precede the
generation's durable publication, and no partial completion may become authoritative.

The comparator does not verify output hashes, generation hashes/existence, checkpoint payload metadata/config,
record identities, admitted epochs, predecessor hashes or fresh-container ids. `walk()` follows mutable old
`state.json` files without verifying the saved predecessor digest and has no strict decreasing/acyclic bound.
Use immutable inherited-record snapshots/canonical chain data, bind the exact selected generation and actual
checkpoint payload step/config/format, and validate admission/provenance against launch identity. Require actual,
distinct nonempty container ids for the fresh-container GPU cases; retain explicit CPU-test provenance handling.
Preserve the first-start identity across terminal inheritance rather than presenting old output as newly bound
output. Bind the checker and reaper hashes in the frozen package/launch provenance as well.

A separate real-worker probe advertised a valid generation as step4 while its payload was a valid step2 checkpoint.
The consumer executed two replay updates before generation monotonicity rejected it. It **did fail closed later**;
this is not a false acceptance. Validate metadata versus payload before any optimizer update and record a controlled
continuity refusal. The initial probe run's exception and scratch evidence were retained; the revised audit runner
records the narrower outcome in run2.

## 4. Timing must serialize the actual trained optimizer and validate every added field

Timing lines 79–85 construct a fresh AdamW after training, then serialize it with an empty optimizer state, a fresh
data generator and empty telemetry. The actual worker's checkpoint carries trained AdamW moments and the real
RNG/data/telemetry state. The remote commit probes are sized from this smaller timing payload.

An independent six-step tiny CPU fixture had **24 optimizer state entries and 275453 bytes** in its real terminal
checkpoint, versus **0 entries and 97685 bytes** using the timing pattern (2.8198x difference). This ratio is only
for that tiny fixture, not a Qwen/A100 measurement. Reproduction: `checkpoint-timing-payload-probe.py/.json`.

Capture the real post-update training checkpoint through the actual hook, outside the fixed-work throughput
window, and time the actual serialization/file/hash path and representative commit cost. Ensure its populated
optimizer state is retained. Validate the new dev/artifact timings, serialization/commit timings and checkpoint
bytes as finite/positive and structurally complete; the imported packing validator only covers its original
throughput fields. Check all 18 arm/N/phase configurations, both ranks and fixed seeds. A missing/failed/nonfinite
T configuration must prevent a whole-proof/ledger PASS; the current A–E comparator does not inspect T.

## 5. Fault C needs evidence of actual artifact evaluation work

The worker touches `eval-phase` immediately after `train()` returns (lines 123–129), before run_pilot saves the
trained parameters or starts artifact evaluation. The supervisor faults as soon as it sees that marker. This
proves a TRAINED-to-eval-only boundary restart, but does not locate the interruption inside artifact evaluation.
Move the proof-only fault marker/handshake into actual artifact evaluation after work has begun (or a declared
completed batch), retain its population/phase evidence, and guarantee the worker is still in that phase when
the fault is triggered. Keep the same C scenario and registered proof multiplicities; no new paid test scope.

## Required next handoff

Fold these fixes into the existing authorized free preparation. Return a frozen revision with the actual serial
runner/resources/deadline, complete charged reservation with explicit assumptions, real checkpoint timing, strict
artifact/schema/provenance gates, corrected fault C and meaningful CPU rejection/durability evidence. Re-run the
affected tests/parity only as the changes warrant. Independent implementation/ledger audit precedes any user
proof-cap request. GPU proof/artifact PASS precedes the A100 campaign ledger and separate execution-cap approval.

No reviewer GPU call, deployment, stop, operator retry, commit or push occurred. Source and historical evidence were
not edited by the reviewer; all mutations for rejection probes were confined to new reviewer-owned scratch copies.
