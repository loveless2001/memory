# Re-timing v2: one deployment and one profile cleared

The sampler cleanup blocker is closed at commit `8db8520`. Clear **one deployment
and, only after successful deployment, one spawn** of group
`p2p5-l40s-profile-v2`, followed by its existing collector through terminal state
and verified shutdown. User gravity 21501 already authorizes this option-A
re-timing under a fresh `$3` envelope. No additional user confirmation is needed.
This is separate from the development-test envelope and does not authorize a
retry, rescue, extra configuration, concurrency test or training campaign.

## Verified repair

The only changed function bodies from reviewed `307a159` are
`start_gpu_sampler` and `stop_gpu_sampler`; the rest of the profile, source
binding, budget, producer, reaper and collector bodies retain the accepted
baseline. The sampler now records query, 500 ms cadence, output path, start/end
epochs and container timezone information. Diagnostic start/stop failures stay
in metadata and do not gate timing usability.

Independently reran all four targeted suites: **93 tests passed in 50.08 s**,
including the real process that ignores SIGTERM and is killed and reaped.
Additional direct probes of the actual cleanup function show:

- The prior wait-timeout/kill-`ProcessLookupError` counterexample is contained;
  final wait reaps with rc0 and preserves the error record.
- If terminate, both waits and kill all fail, status truthfully says not reaped
  with rc=None; no exception escapes.
- An unavailable sampler produces JSON-serializable not-started metadata and
  start/end timestamps.

These are CPU-local checks, not a remote GPU run. The historical shared
whole-app self-stop proof remains applicable because that logic is unchanged.
No new paid proof was run. Tracked implementation files match the frozen commit.

## Frozen identity and fresh state

- v2 runner:
  `31e16ed24118c40f60da0341a99016e5db55ece3eb02b2083414a74f25df4f87`.
- Unchanged profile script:
  `b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c`.
- Unchanged shared reaper logic:
  `32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c`.
- Parity-tested memsub:
  `b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085`.

Read-only prelaunch checks completed at **2026-10-06 15:02:28 UTC**: neither v2
guard nor attempts Dict exists, there is no v2 app row, and the fresh local output
directory is absent. All v1 historical evidence, app identities and dictionaries
remain outside this new group.

## Reservation and execution

Keep the full **`$2.3844246` reservation** within the fresh `$3`: GPU lifetime
`$1.9563936`, reaper ticks `$0.009647`, full image-build allowance `$0.168384`
and margin `$0.25`. This preserves the accepted deadline/scheduling/stop-latency
and build-overuse assumptions. It is not a platform-enforced spending limit.
Do not discard the build reserve based only on a cache expectation or transfer
the development envelope's unspent funds.

From a clean project tree, save a new deployment log and exit status:

```sh
.venv/bin/python -m modal deploy modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py
```

Only after success, invoke once:

```sh
.venv/bin/python modal-runners/modal-m4-sgm-p2p5-l40s-timing-profile-v2-after-speedup.py spawn
```

Retain deployed app ID, call ID, full expected identity and absolute deadline
before collecting. The unchanged matrix is learned/memory_off at N32, batch16,
training seed99, filler0/40: two warmup plus eight measured synchronized complete
forward/backward/optimizer updates per configuration, and one dev batch at
seed4242. Forty updates total, full-gradient token-serial FP32, TF32 off;
checkpoint/resume options stay off. The overall deadline is 2700 seconds after
producer launch, with the existing startup/child watchdog, guarded attempt,
independent reaper and collector shutdown verification.

First deployment error or profile OOM/error/preemption/unusable result ends this
clearance; retain evidence and stop. No automatic retry, precision change,
detaching, offload, batch reduction, replacement population or extra sampler run
is cleared. Missing diagnostic samples do not authorize a repeat. Collect raw
profile/progress/exit/sampler artifacts and verify stopped/unlisted app state,
zero tasks and zero matching containers independently.

## Result boundaries

The resulting update/dev timings and memory are measured evidence for these four
shapes. V2 includes a background sampler whereas v1 did not; its overhead is not
separately measured. Report phase-window GPU activity descriptively, with coverage,
cadence and failures; do not infer spatial occupancy or concurrent capacity from
activity percentage alone.

Repricing must go to a fresh output and retain the original ledger. Incorporate
the actual 52/20 artifact-evaluation batch workload if using run_pilot; label
unmeasured controls/N16, I/O and app topology assumptions. Four shapes do not
establish a real whole-campaign cost or empirical upper bound. GPU resume,
learning, full-campaign equivalence and packing economics remain unverified.

Evidence: `codex-261006-p2p5-v2-8db8520-tests.log`,
`codex-261006-p2p5-v2-8db8520-sampler-checks.json`,
`codex-261006-p2p5-v2-8db8520-prelaunch-state.json`, and the retained
`307a159` baseline checks and initial cleanup counterexample. This audit performed
local checks/report writes and read-only Modal calls only; no deployment or paid
invocation was performed by Codex.
