# B3 terminal audit: valid negative, shutdown verified

**VALID_NEGATIVE.** The single authorized B3 campaign completed 1500 updates on training seed 0 and reused
development seed 4242. Final normal memory scored **8/256**, bank-deranged memory **8/256**, drop **0**.
Both registered exploratory thresholds fail (>=12 correct AND >=6 derangement drop). No demonstrated memory
use for this shift2 fill+anchor bundle and recipe. This does not establish a general inability of Qwen to use
memory, or the reason this recipe failed. Equal aggregate counts do not establish equal predictions or logits.

## Independent terminal evidence

The fresh read-only capture ran 2026-10-10 06:30:44–06:31:21 UTC. It fetched 11 Volume files, including the final
checkpoint (the owner's collection intentionally skipped it), and looked up only existing Modal objects.
No deployment, spawn, training, model construction, forward/backward, restore, stop, or remote write occurred
in this audit. User go #22535 authorized this one campaign; wait #55 triggered this terminal audit.

- App `ap-uV0nVE4wGpjtep7vRs8tot`, call `fc-01M4HWABMJ4SHV1CRX72J7WTMM` returned rc 0 from start-1,
  wall 12209.196365 s, zero Volume commit errors, no terminal-write/guard-cancel diagnostics, and pinned
  torch 2.7.1+cu126 / transformers 4.55.2.
- The Dict has only start-1, the original deadline, and a completed terminal marker. Start-2/start-3 are unused.
  Deadline and start-1 are identical to the independent launch snapshot; the trainer has one start row with
  no restore. Completion precedes the immutable 09:34:47 UTC deadline.
- All 86 source/input files retained at launch still match the cleared package `2efd2b0` byte-for-byte.
  Owner terminal records at capture are `cccf23751c29c3234bb97a3d903f5c6dccce7719`; this adds records, not code.
  Trainer, source-tree and input-manifest identity match the remote identity and final manifest.
- Telemetry has exactly 16 development evaluations (0 through 1500 every 100 updates), 150 training log rows
  (0 through 1490 every 10), 166 total rows, valid registered evaluator schema and finite recorded training
  scalars. The independently recomputed registered classifier exactly matches `b3_result.json`.
- Checkpoint `resume.pt` is update 1500, 44,229,525 bytes, SHA256
  `c9bb22935002e5fb09f2f5a6366a1bc7fd63ca25bb84737911ef3f879c75e198`.
  Its identity/config match, all tensor state is finite, CPU/CUDA/data RNG state is retained, and its telemetry
  equals the exact prefix before the final evaluation. All 44 active AdamW states have update counter 1500.
- All 46 adapter/head tensors exactly match final safetensors SHA256
  `7e0b4999af3a9e961dfd2d939a68b7e0e905821a557e749818dd929a52f9d295`, also bound by the final manifest.
  All 16 q/k/v/beta projection weights are 2048 inputs wide. No unregistered fixed checkpoints exist.
- Fresh files agree with the owner's collected files wherever those are present. Trainer stderr is empty.
  Original watcher PID 254336 no longer exists.

The offline verifier passed 686 artifact/provenance checks under a 2000M MemoryMax / zero-swap scope and
60-second timeout. No test suite or mutation campaign was rerun. The first audit-script attempt compared a
checkpoint tuple `checkpoint_steps=()` with JSON `[]`; after recording this sole representation difference,
the comparison used JSON normalization. That failed audit attempt and its script/log are preserved separately;
no campaign artifact changed and no experiment was retried.

## Shutdown

The watch returned on call completion. `cleanup.json` records `stop --yes` rc 0 and a separately verified second
check after a lagging stopping/task-count observation; cleanup elapsed 29.217711 s. Fresh independent Modal
queries confirm **stopped app, zero tasks, zero B3 containers**, and an empty account container list.
App stopped at **06:28:37 UTC / 13:28:37 Bangkok**, well before the deadline. Shutdown PASS is based on these
queries, not only the stop acknowledgement or watcher exit. The launch audit's suggested follow-up filename
`final_shutdown.json` was inaccurate: this runner's durable receipt is `cleanup.json`.

## Scientific wording corrections sent to the owner

The data support the negative screen, but the as-found readout at cccf237 needs these corrections (channel #22603):

1. Name **training seed 0** and **development seed 4242** separately. Reused, inspected development data and one
   training seed define this exploratory scope.
2. Class-average beta and alpha are nearly steady; **parameter freezing is not established**. After update 300,
   the logged beta class-mean ranges are key 0.00041665, value 0.00036475, filler 0.00023963. At the final logged
   update, all four layers have positive beta parameter update norms (0.020518, 0.003728, 0.00000746, 0.00002903).
   Alpha ranges after update 540 are L6 0.00002131, L13 0.00010781, L20 0.00026024, L27 0. The last values are
   0.018274, 0.018993, 0.018278, 0.017986. L27 output/alpha zero updates have the expected taskhead graph reason;
   they do not show a failure to update the direct raw-read route.
3. The prior offline probe used the **shift1 initialization runtime**, including V+K side-channel features.
   It motivated shift2 but did not certify decoder performance/key-feature recovery in a live shift2 runtime.
   The inspected probe source explicitly requires feature_shift=1; the retained prior proposal audit states this
   boundary. B3 tests the full shift2 bundle with changed width/initialization and phase-dependent query context.
4. The difference from B2's previously audited 5/256 is descriptive. The episode CI half-width is about five
   correct, but no formal between-arm test or saved paired predictions establish equivalence or a benefit.

Final absent-read weight is 0.10474693: the endpoint is in the kept band, but the step-300 value 0.21027077 means
it was not kept at every evaluation. The last ten logged task-CE mean is 4.15565510 versus ln64=4.15888308.
Median logged short/long-phase update durations are 6.486537/10.558967 s. These descriptions do not identify a
causal mechanism for the failed screen. The owner has been asked to replace the frozen-gate interpretation.

## Billing and stop point

Independent hourly and daily reports agree on **$6.64800992 current app-attributed usage**:
L40S $5.41233272, CPU $0.52513505, Memory $0.71054215 (resource rounding may differ by $0.00000001).
The 03 UTC hour reports only $0.71856024 total, compared with about $2.3952 for a full hour; its GPU charge
implies roughly 1080 seconds using the full-hour ratio despite about 3310 seconds from container start to 04 UTC.
This suggests incomplete/backfilled reporting. The wall-time ledger estimate is roughly $8.30, conditional on
its stated resource/rate assumptions. Neither value is a settled all-resource invoice or proof of final spend.
Storage, transfer and late backfill remain unverified. The original $17 approval and $16.3035352 conditional
reservation are preserved; no budget reset or further compute is authorized.

Training/terminal wait #55 is closed. Arrange **one read-only billing recheck after 60 minutes**, then report any
backfill without running additional compute. Claude owns readout wording corrections and the proposed closing
write-up; no additional scientific or paid action follows from this audit. All source, checkpoint, final weights,
raw reports, receipts, initial failure evidence and verification files are retained and sealed with `SHA256SUMS`.
