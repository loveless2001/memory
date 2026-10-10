# Option B packing terminal audit

Accepted the complete bounded packing result at `6686215`, bound to launched source `57aad8581579c9fd17ba70490e0d817567cedb59`, packing script SHA `873bca626b195775f07734d1d470cf71eadbc36ec553fa26889fb77c8407f247`, unchanged dev runner `5c1e287e…`, memsub `b87a767b…` and app `ap-uPN6X6TfZ7Yv9lCaLHAkx7`. All 32 committed evidence files byte-match. The remote child and wrapper exited zero; the complete report reconciles with seven individual worker records, 56 updates (14 warmup, 42 measured), four stdout summaries and all 666 finite sampler rows. Remote wall time was 337.988 seconds; client wall time was 343.960 seconds.

The corrected primary statistic independently reproduces complete measured updates divided by the elapsed union span, rather than summed individual reciprocal means:

| Test | Worker mean seconds/update | Complete measured updates | Elapsed span, seconds | Primary updates/second | Speedup vs phase k1 |
| --- | --- | ---: | ---: | ---: | ---: |
| P2, k1 | 9.594634 | 6 | 57.567862 | 0.104225 | 1.000000 |
| P2, k2 | 9.912906 / 9.953768 | 12 | 59.725535 | 0.200919 | **1.927747** |
| P1, k1 | 5.921785 | 6 | 35.530751 | 0.168868 | 1.000000 |
| P1, k3 | 8.281475 / 8.339590 / 8.387395 | 18 | 50.324435 | 0.357679 | **2.118101** |

The P2 k2 result meets the pre-stated ≥1.5 descriptive threshold for considering a priced design if requested. P2 workers individually took about 3.3–3.7% longer; P1 k3 workers took about 39.8–41.6% longer while aggregate throughput increased. Secondary fractional-window and reciprocal-mean statistics also reconcile; the primary remains the decision statistic. This is short, fixed-order, single-host evidence at seeds99+rank, N32/batch16 and six measured updates per worker. It does not establish repeated-run uncertainty, sustained campaign throughput or scientific learning/correctness results. GPU and campaign resume remain unverified.

The independent UTC CSV alignment reproduces mean sampled GPU utilization 35.6% / 81.6807% for P2 k1/k2 and 37.5143% / 89.3366% for P1 k1/k3, with 115/119/70/101 in-span samples. Corresponding NVML memory-used maxima are 28,373 / 56,803 / 18,185 / 54,508 MiB. PyTorch per-worker allocation is approximately 26.8 GB in P2 and 17.0 GB in P1; values vary slightly by seed. NVML memory-used and PyTorch allocation are distinct counters.

[NVIDIA defines GPU utilization](https://docs.nvidia.com/deploy/nvidia-smi/index.html#utilization) as sampled time with at least one executing kernel. These observations do not measure spatial SM occupancy or determine why kernels were absent. They support the descriptive packing comparison but not a demonstrated CPU bottleneck. Summing observed P2 peaks advises against assuming k3/P2 fits; that configuration was not tested. Absolute timestamps use the declared UTC offset; underlying sampling windows can straddle interval endpoints.

At [Modal list prices](https://modal.com/pricing), the requested A100/8-core/64-GiB rate divided by the observed primary training rate gives approximately $0.009027/$0.004683 per update for P2 k1/k2 and $0.005572/$0.002631 for P1 k1/k3. These are **training-only list-price proxies**, excluding model startup, dev/artifact evaluation, controls, N16, readings, I/O, packing transitions, build, reapers, failures and concurrency topology. The cross-host A100/L40S comparison also changes CPU/RAM allocation, thread settings and timing harness; it does not isolate a hardware effect. The $75–85 full-campaign forecast is illustrative and unvalidated until the actual packed schedule, runner and ledger are bound and audited. No new design or execution scope is authorized by this audit.

Independent read-only live verification completed at 2026-10-06 15:56:36 UTC: the packing app is stopped, tasks0, no matching containers; lifecycle stop is 15:52:04 UTC (22:52:04 Bangkok). Saved app-state and verification evidence agree. This shutdown claim applies only to the approved packing app, not other workspace experiments.

App-only reported billing advanced from the committed **$0.31267055** snapshot to **$0.32053572** at the audit refresh. It remains an unsettled snapshot. The console has no `Building image` line, which supports apparent reuse without proving a settled zero build charge. Retain the full **$1.98 reservation** in the separate **$2 envelope** pending reconciliation. Unused reserve does not authorize a retry, larger experiment or campaign.

Historical v1 timing/protocol bytes remain unchanged. No paid job, deployment, stop or journal mutation was issued by this audit. Reproducible source, arithmetic, sampler, lifecycle and billing evidence is in `codex-261006-p2p5-packing-6686215-terminal-check.py/.json` beside this report.
