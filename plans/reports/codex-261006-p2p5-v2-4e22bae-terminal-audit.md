# P2.5 v2 re-timing terminal audit

Accepted the bounded timing profile in `4e22bae`, bound to source `8db8520`, candidate memsub SHA `b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085`, app `ap-Fs085d1acB4y3NbGlwEz3W` and call `fc-01M48WAHVDC6610H89B5B382V9`. This accepts the completed profiling experiment only. No campaign, packing experiment or additional spending is cleared.

The independent checker byte-compares terminal evidence and launch provenance with their commits, validates the source identity and profile SHA `ff2a7a437a3a1ae43d8c720522ff97e130650d82b2035d6c69efbc95083f862b`, and reconciles all 50 progress rows: 40 updates, four configuration starts, four dev evaluations, start and end. Each configuration has two warmup and eight measured updates. Child exit is zero; completion occurred within the watchdog and app deadline. Total profile wall time was 344.308 seconds. Historical v1 evidence, including the malformed legacy verification record, the preregistration and registered grid remain byte-identical to the accepted original evidence.

| Configuration | Mean seconds/update | v1/v2 ratio | Peak allocated GB |
| --- | ---: | ---: | ---: |
| learned, filler 0 | 9.443441 | 1.459620 | 16.981406 |
| learned, filler 40 | 14.882220 | 1.439317 | 26.779278 |
| memory_off, filler 0 | 2.204492 | 0.982795 | 2.716089 |
| memory_off, filler 40 | 3.410441 | 0.983297 | 2.716155 |

These are separate short runs at N32, batch16, seed99, full-gradient FP32 with TF32 disabled. The speed ratios apply to these measured updates. The memory-off updates took about 1.7% longer. Peak allocation is approximately unchanged, rather than byte-identical: v2 exceeds v1 by 182,272 and 319,488 bytes for learned and 512 bytes for each memory-off phase. Sampler overhead was not independently measured and v1 had no sampler. There are no scientific accuracy or learning results in this profile.

The 698 finite CSV samples reconcile with the UTC timestamps, declared 500 ms cadence, sampler epochs and clean sampler termination. Using the union of the eight individual measured-update intervals, inferred as completion timestamp minus duration, the learned GPU-utilization means are 16.08% (150 samples) and 15.874% (238 samples). The peer's contiguous phase window includes one intervening sample for phase 1 (151 samples), with the same rounded 16.1% result. Memory-off means are 25.389% and 26.037%; dev counts and means also reconcile. NVML memory-used peaks differ from PyTorch allocated-memory peaks because the counters measure different things.

These sampled utilization observations do not establish why kernels were absent, SM occupancy or whether multiple runs can share a GPU efficiently. A CPU launch bottleneck remains a hypothesis informed by the earlier profiler. See [NVIDIA's utilization definition](https://docs.nvidia.com/deploy/nvidia-smi/index.html#utilization). Interval boundaries are inferred and underlying NVML averaging windows can overlap their edges.

Independent live verification at 2026-10-06 15:24:51 UTC found the app stopped, tasks zero, no matching containers and a lifecycle stop timestamp of 15:17:55 UTC. Guard and attempt dictionaries bind the same app/call and exactly one profile attempt. The original first terminal collection remains `shutdown_unresolved`: it retained stopped/zero-container observations but no task count, so its failed verification cause cannot be established. The later idempotent collection verified shutdown; its repeated stop command returned an error, whose precise cause is not established by the retained error string. This collection retry did not constitute a compute retry.

The saved 52-memory/20-memory-off artifact-evaluation ledger exactly matches pure re-execution. Separately implemented arithmetic across the registered 18 cells reproduces:

| Planning basis | Total USD | Cell GPU hours | Longest modeled cell hours |
| --- | ---: | ---: | ---: |
| Estimate | 158.376431 | 64.046898 | 5.067861 |
| Reserve, labeled `bound` by the script | 270.519241 | 107.531845 | 7.161667 |

The comparable v1 ledger at the same 52/20 evaluation workload is $216.919622 estimated and $368.272410 reserved. The original 16/16 v1 ledger remains unchanged and reproduces exactly. The new values rely on learned timing proxies for control arms, unmeasured N16 scaling for the estimate, startup/evaluation/build allowances, a single modeled reaper and a 1.4 factor plus margins. They are planning figures, not a validated execution upper bound. Five/seven hours describe the longest modeled cell; other cells differ. The actual campaign runner, concurrency topology, I/O and GPU checkpoint/resume consumer still require preparation and audit. CPU resume checks do not establish GPU or campaign resume. Preemption retries are not priced.

Live reported usage for the scoped profiling app was $0.23930796. This is an app-only billing snapshot, not a settled all-in total. Retain the $2.3844246 reservation within this separate $3 envelope. No unused reserve grants authorization for further work.

Verification artifacts: `codex-261006-p2p5-v2-4e22bae-results-checks.py/.json` and `codex-261006-p2p5-v2-4e22bae-live-terminal.py/.json` in this directory. Remote operations were read-only; no GPU job, deployment or stop was issued during this audit.
