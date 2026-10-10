# P2.5 L40S timing/fit profile accepted; campaign remains unapproved

Reviewed #gravity 21467 and evidence commit
`2fda0d42c8566875af355dc97db2fdc3bac743d1`. **The completed four-configuration
L40S timing/fit profile is usable and accepted.** Shutdown is independently
verified. The campaign arithmetic reproduces, with the qualifications below;
it is not a verified campaign spending bound or clearance to execute.

## Independent artifact checks

All 14 files added by 2fda0d4 match their committed bytes. Recomputed source
identity matches the saved launch identity and the frozen 508443c audit:
runner `6406e641…`, profile script `b5b0746a…`, shared logic `32bb3a3a…`,
memsub `048df640…`. Grid and prereg bytes are additionally hashed in this audit.
The profile file SHA256 is
`bbdcbaae417b2d8fb77e3d8748e1a718b7bbf2a818071779dcdb4bc3790d8a13`.

Child exit is 0, stderr empty, profile status complete. Collected return data
and the fetched profile agree exactly. The audited production validator
accepts the bound source, environment, contract and exact matrix. The 50
progress rows contain start, four config starts, exactly 40 completed updates,
four dev-batch completions, and complete end in the prescribed order.
Each configuration has update IDs 0–9; its ten progress timings exactly equal
the two warmups plus eight measured values. Recomputed means, per-update peak
memory maxima and dev timings match the profile. The 445.405699-second wall
matches the progress span within one second and is below the 1800-second bound.
No accuracy or predictions appear in the exported profile.

The synchronized timing hook runs after forward/backward/optimizer work.
The unchanged pretrained loader verifies pinned model files, uses FP32 and
disables CUDA matmul and cuDNN TF32. The saved environment reports Python
3.12.10, torch 2.7.1+cu126, CUDA 12.6, NVIDIA L40S and matmul TF32 false.

| Configuration | Mean seconds/update | Peak allocated GB | Peak GiB | Dev batch seconds |
|---|---:|---:|---:|---:|
| learned, phase 1 | 13.783831 | 16.9812 | 15.8150 | 8.312449 |
| learned, phase 2 | 21.420230 | 26.7790 | 24.9398 | 8.606311 |
| memory_off, phase 1 | 2.166563 | 2.7161 | 2.5296 | 3.328643 |
| memory_off, phase 2 | 3.353476 | 2.7162 | 2.5296 | 3.338591 |

GB here means decimal bytes / 1e9. The observed phase-2 learned allocation
exceeds 24 GiB under this execution. No 24 GB GPU was measured; retain this
trace-specific statement and the frozen L40S choice. This establishes fit and
short-update timings for these two arms at N32/seed99, not long training,
other arms/N16, learning, accuracy, routing use or a screen pass.

## Shutdown and billing

Independent read-only live checks at **2026-10-06 11:28:23–11:28:31 UTC**:
app `ap-w0KWMJST1Dfg5ipxZQV7QV` is listed **stopped**, **tasks=0**, with
**zero matching containers**. Lifecycle stop is **11:21:54.922382 UTC**,
matching the separately saved stop verification. Listed-stopped and unlisted
snapshots both satisfy the audited shutdown rule; this snapshot is listed.
The guard remains bound to the saved app/call/deadline with only start1;
the attempts Dict contains only the original attempt-1 claim.

The live app-filtered hourly usage matches the committed snapshot:

| Scope | Reported USD |
|---|---:|
| Completed profile app | 0.30996920 |
| Retained failed deployment | 0.00008124 |
| Accepted CPU reaper proof | 0.00012308 |
| Total | **0.31017352** |

This reported total is below the same approved $3 cap. It is not a final
invoice; keep billing provenance and reconcile any later backfill. Successful
cheap completion does not create authorization for more work from the unused
profile cap. No unrelated app was modified or stopped.

## Campaign arithmetic and limits

Loading the new ledger module and invoking `ledger()` without its output-write
entrypoint reproduces the committed JSON exactly. A separate calculation
using the 18-cell universe and raw update/dev timings independently reproduces:

| Current JSON basis | Cell GPU hours | Planning total USD |
|---|---:|---:|
| estimate | 87.517194 | 214.355709 |
| bound | 146.798391 | 364.180963 |

Both contain 18 unique cells. The longest claimed cell life is 7.07847 hours
for estimate and 9.9765 hours for the bound basis. The learned N32 proxy gives
24493.945845 seconds of training and 25482.5 seconds of wall before the 1.4
factor. The price inputs match the current
[Modal pricing page](https://modal.com/pricing): L40S .000542/s,
CPU .0000131/core/s, memory .00000222/GiB/s. These rates validate the arithmetic
inputs, not the future work or runtime assumptions.

Required wording and planning qualifications before a future campaign cap:

1. Label `bound` as an **assumption-based planning reserve**. Learned timings
   proxy single_cell, random_fixed and oracle; N16 and long-running training
   were not profiled. A 1.4 multiplier does not establish an empirical upper
   bound. Preserve the historical ledger when adding a clearer revision.
2. Two filler points determine a line exactly. Their near-zero intercept
   supports reporting the fitted slope, but does not establish linear scaling
   at N16 or across arms. Report N16 step-count scaling as an explicit estimate.
   The roughly 84% difference is a descriptive between-arm timing contrast;
   it is not a kernel or hotspot attribution.
3. Bind the eventual charged ledger to the actual campaign runner, complete
   artifact-eval intervention/batch counts, parity work, telemetry/parameter
   serialization and I/O. If existing `run_pilot` final evaluation is reused,
   it executes three 16-batch interventions plus four train batches for memory
   arms (52 batches), and 16+4 for memory_off (20), rather than the ledger's
   assumed 16 artifact batches. The future runner could choose a different
   prereg-consistent artifact workload, which must be explicit.
4. Bind reaper costs and stop grace to actual app lifetime and concurrency.
   The current reaper term uses the longest cell, not a specified whole-app
   schedule; serial execution, queueing or multiple apps changes that basis.
   Readings teardown, build requests/overuse, network/volume charges and the
   fixed margin also need the actual execution topology. The current $5 margin
   is a planning allowance, not evidence that all charges have been bounded.
5. Retain the explicit no-retry preemption policy. These figures do not price
   completing lost cells or the probability of obtaining complete seed pairs.

The profile invalidates the provisional $30–60 planning expectation for this
implementation under the stated proxies. Further options may be discussed
without compute. No new profile, registered training cell, artifact/reserved
population reading, rescue change or full campaign is authorized by this audit;
prereg Gate 3 still requires implementation audit and a fresh scoped user cap.

Evidence: `codex-261006-p2p5-2fda0d4-results-checks.py/.json` records committed
byte comparisons, all consumed hashes, progress reconciliation and independent
arithmetic; `codex-261006-p2p5-2fda0d4-live-terminal.json` retains live shutdown,
claim and billing rows. This audit performed local arithmetic/report writes and
read-only Modal queries only. No GPU rerun, registered cell or readings run.
