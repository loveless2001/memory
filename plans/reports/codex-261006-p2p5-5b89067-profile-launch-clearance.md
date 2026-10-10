# P2.5: remote self-stop proof accepted; single L40S profile cleared

Reviewed #gravity 21461 and evidence commit
`5b89067a82f97709d5cfab305efe20844bff2a19`. **The real CPU self-stop proof is
accepted. Clear the already-authorized single preemptible L40S timing/fit
profile under user 21446's total $3 scope.** R1's outstanding runtime stop
permission check is closed for this shared path; R2/R3 and the prior local
deadline/cleanup checks remain closed. No new user permission is needed.

This clears one deploy/spawn sequence using the unchanged audited code from
`9e7b897`, now at evidence-only HEAD `5b89067`. It does not authorize a second
profile, automatic retry, revised matrix, laptop retry or the 18-cell campaign.
No GPU deployment, build or profile was launched by this review.

## Actual proof evidence

The proof app is **`ap-i4m6Qy73vjSs8LVFZza8Z6`**, deployed at
2026-10-06 10:50:03.231354 UTC. Its bound deadline was
`1791283924.0450027`; the live lifecycle confirms stop at
`1791283925.697458`, **1.6524553 seconds after the deadline**.

Independently verified the committed files, their exact source bindings,
deployment and console exit-status records, retained live observations,
and this bound server-side marker:

```text
M4SGM_REAPER_STOP app=memsub-m4-sgm-p2p5-reaper-proof bound=ap-i4m6Qy73vjSs8LVFZza8Z6 reason=deadline passed t=1791283925
```

The server log also records stopping through the Python client. The saved
report contains PASS, no errors and no fallback. Its observed sequence
transitions from not stopped to the same stop time independently obtained
from Modal. The frozen PASS path issues no local stop. The lifecycle's
`stopped_by` workspace-user label alone would not distinguish a container
client from a local client; the shared code, marker, timing and execution
record supply the relevant additional evidence.

The proof report omitted its `verify_stopped` payload. Preserve that gap in
the historical report; do not rewrite it as if it had saved the payload.
Claude retained a separately labeled post-hoc check. This review additionally
made an independent, read-only check at **10:55:11 UTC** and saved its raw
matching rows/lifecycle in `codex-261006-p2p5-5b89067-live-shutdown.json`:

- The exact app is listed **stopped**, with **tasks = 0**.
- There are **zero matching live containers**.
- Its live lifecycle stop time matches the saved report exactly.

The consumed artifact hashes and recomputed checks are saved in
`codex-261006-p2p5-5b89067-proof-results-audit.json`. The six original committed
proof files were compared byte-for-byte with `git show 5b89067:<path>`.
No CPU proof rerun was performed.

This establishes successful self-stop using the shared code/container path
on this Modal deployment. It does not establish universal scheduling latency,
termination guarantees, GPU fit, training performance or scientific validity.

## Budget and launch preflight

The read-only preflight beginning at **10:56:22 UTC** found neither profile
guard nor attempts Dict created and no local `p2p5-l40s-profile-v1` output
directory. Those observations are retained in
`codex-261006-p2p5-5b89067-launch-preflight.json`.

App-filtered reported proof usage is now **$0.00012308**: CPU $0.00009197
and memory $0.00003111. This updates Claude's earlier $0.00009671 snapshot;
it is not a final invoice or an assertion that every build charge has settled.
For admission, continue retaining the **entire $0.052740625 proof reserve**
alongside **$2.3844246 profile reserve**, total **$2.437165225 <= $3**.
Do not reset the approved total to a fresh $3 for the GPU run.

The profile ledger's L40S/CPU/RAM rates match the current
[Modal pricing page](https://modal.com/pricing). Its nominal schedule,
stop-latency and build/resource overuse allowances remain explicit assumptions;
the observed proof validates the stop path, not worst-case platform latency.
The cleared GPU option is preemptible. Infrastructure rescheduling remains
distinct from a permitted second profile: the claim refuses a rerun, and the
independent app stop covers the paid lifecycle.
[Failures/retries](https://modal.com/docs/guide/retries),
[preemption](https://modal.com/docs/guide/preemption).

## Frozen launch identity and execution

- Runner:
  `e26013e6e34545552eb7d6d4fc8e07af2e1fc8c927f5e38818714a3de4069349`.
- Profile script:
  `b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c`.
- Shared stop logic:
  `32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c`.
- Memsub source:
  `048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`.

From `/home/lenovo/projects/memory`, deploy once, preserving its output and
exit status, then invoke the audited spawn once:

```sh
.venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py
.venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py spawn
```

Retain the actual deployment app ID, launch identity, absolute deadline and
call ID. The fixed workload is four fresh configs, two warmup plus eight
measured updates each (40 total), four dev-batch timings, batch16/N32,
seed99/dev4242, the registered full-gradient FP32 token-serial contract.
No accuracy output or registered/artifact/reserved populations are added.

Use the existing collector for terminal evidence and shutdown:

```sh
.venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile.py collect
```

On the first OOM/error/preemption/unusable result, preserve the exit record,
profile JSON and progress and stop; do not retry or alter the workload.
Finish with verified stopped/unlisted state, zero tasks and zero matching
containers on the saved profile app ID. Review the collected bound files
before turning timings/fit observations into any full-campaign cost proposal.
