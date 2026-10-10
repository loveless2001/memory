# B3 single-campaign launch and first-start audit

Verdict: PASS for the observed launch and first-start mechanics at cleared commit
`2efd2b09d9371cd1861128eb7781b4ff9a433577`. Training is active; no scientific readout or shutdown verdict yet.

User authorization is channel message #22535 (`@claude go`), responding to the specific $17 decision described in
#22526/#22527. Claude owns the single launch and existing watcher. This audit adds no dispatch, retry, deployment,
extension, extra seed, training process or additional watcher.

## Retained launch and live evidence

- Precheck, deployment and spawn logs report exit 0. The retained single spawn records app
  `ap-uV0nVE4wGpjtep7vRs8tot` and call `fc-01M4HWABMJ4SHV1CRX72J7WTMM`.
- Live read-only app/container queries show one deployed app, one task and one container,
  `ta-01M4HWABYE68TY018WJCDFM5GR`. Their JSON is retained in `live-apps.json` and `live-containers.json`;
  these queries preceded the scoped Dict/Volume snapshot at 03:06:43–03:06:54 UTC.
- The existing FunctionCall times out on a nonblocking `get(timeout=0)`, consistent with running.
  The start Dict contains only `campaign-deadline` and `start-1`, bound to that container. Start-2 and start-3
  are unused; no terminal marker exists at this snapshot.
- `run.json`, the Dict and Volume `campaign.json` agree on the immutable deadline:
  **2026-10-10 09:34:47.656670 UTC / 16:34:47.656670 Bangkok**.
- Trainer start evidence records start 1 with `resume_step: null`. The remote identity matches the local
  cleared trainer SHA `3f653b79fa70b5b27a3fc714d448991952d23e4710c8bcf31f52ace1b8b466b8`, memsub tree SHA
  `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`, and input-manifest SHA
  `4e89b95adcff68b73fecb2f071c3fe17498c7e62fd1a97ac04f77691b5fc0bb0`.
  Configuration is seed 0, 1500 updates, feature_shift=2, CUDA, and filler schedule [[0,0],[1000,40]].
- Initial development evaluation is 5/256. The step-0 training row records finite loss and positive q-projection
  update norms at all four adapted layers. This proves initial execution only. The first recorded step duration
  is not a throughput profile or completion forecast; it precedes the filler-40 training phase.
- No `resume.pt` or `b3_result.json` is present in the committed snapshot. No final bank-derangement gate can be
  assessed. Layer-27 output/alpha null gradients in this taskhead telemetry do not establish an unexpected failure.
- Original watcher PID **254336** is alive with SID 254336 and the expected runner `watch` command.
  Its empty log is normal while waiting. No second watcher was launched.

86 retained source/input files match the cleared commit byte-for-byte, including all tracked memsub files,
runner, trainer, stage-A dependency, focused tests, input manifest and handoffs v1/v2/v3. Tracked inputs are clean.
Untracked run outputs and B1/B2 parameter artifacts are listed in `git-status.txt` and were not modified.

## Budget and shutdown boundary

The campaign metadata preserves the authorized $17 decision and conditional reservation $16.3035352,
with $0.6964648 headroom. Campaign + grace + poll lag + cleanup is 23880 seconds. The corresponding conditional
cleanup-window end is **09:42:47.656670 UTC / 16:42:47.656670 Bangkok**.
CPU overuse, storage/transfer, outages, crash loops and network/stop tails remain the disclosed conditions;
this audit establishes neither an all-resource hard ceiling nor settled expenditure.

Worker startup, resumed execution and billing are distinct from the scientific screen. The final registered
screen requires >=12/256 and paired derangement drop >=6; only the completed one-seed development artifacts can
support that exploratory classification. The live package-version guard exists, but its returned versions and
final commit/error fields will be checked when the call returns.

## Next trigger and follow-up

Register an agentchattr wait on PID 254336 exiting (480-minute timeout); the wait does not start a new process.
On that trigger, read the latest channel instructions, inspect `watch.json`, `call_result.json` and
`final_shutdown.json`, and independently confirm stopped/unlisted app AND zero tasks AND zero containers.
Coordinate with Claude's existing wait #53; collect/audit final artifacts and billing without duplicate dispatch.
A wait timeout is a trigger to inspect state, not a scientific or operational failure verdict.

The read-only snapshot script used only existing-object lookups (`create_if_missing=False`), Dict reads,
Volume listing/small-file reads and the nonblocking existing-call lookup. A 60-second host timeout bounded it.
No model weights or checkpoint were fetched; no GPU/CPU worker was invoked by this audit. Local checks retained
and verified provenance without rerunning the model tests or mutation campaign.

See `checks.json`, `input-manifest.json`, `launch-logs/`, `live-snapshot.json`, `live-snapshot/`,
`watcher-process.txt` and the included audit scripts for reproducible evidence. `SHA256SUMS` seals retained files.
