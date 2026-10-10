# Final training artifact and shutdown audit — gravity21704

**Verified: 17 COMPLETE + valid cells, one unchanged FAILED cell, all nine training slot apps stopped.** Read-only snapshot completed **2026-10-07 13:38:18 UTC**, environment `main`. This closes the training audit; it does not clear readings or an amendment. [Machine-readable evidence](terminal-verification.json), [verification script](verify-terminal.py), [log](verify-terminal.log) and raw remote listings are retained here.

All seventeen COMPLETE artifact bundles independently pass the original frozen shared validator: output digests, strict finite JSON, configuration/population bindings, per-example coverage, metric consistency, telemetry counts and schemas, trained tensor names/shapes and finite values. Their done.json maps equal their canonical COMPLETE output pointers. Canonical predecessor digest/epoch/identity checks pass. The terminal step1500 checkpoint payload digest was independently checked for **all eighteen cells**, including the failed cell; intermediate checkpoint payloads were not all rehashed.

`learned-n32-s1` remains FAILED for the diagnosed nullable-gradient schema rejection. Its original state, done.json and all seven output hashes are unchanged from the independent diagnosis. No reconstructed COMPLETE pointer or amendment record was used.

Every bound training app is stopped or unlisted, with zero observed tasks and no containers. Admission counts are within four: single_cell-n32 has three; oracle-n32, random_fixed-n32 and random_fixed-n16 have two; the other five slots have one. Slot guards, registry entries and controller app/price/deadline bindings remain unchanged from the launch snapshot. Source remains `537ace8bc30a5ec486e521b6adf7ee3c340abf9f` with no tracked diff.

Readings is deployed and idle, with zero tasks, no containers and no guard/admission names. Under the existing [execution supplement, step6](../../261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-campaign-execution-supplement.md), a FAILED cell makes the reading unavailable without rerun/rescue. [Prereg row1](../../261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/prereg.md) permits no headline at any N when a bound input is invalid. The original protocol outcome is therefore **unavailable**, and reserved readings remain blocked. Any separately authorized post-hoc amendment must preserve this original outcome and the failed evidence.

The existing CPU controller remains bounded by **21:26:57.252974 UTC**. With the frozen readings reserve13826.6s and slack1800s, its latest possible readings candidate is **17:06:30.652974 UTC**. This is a binding constraint, not authorization to spawn, amend or reset the clock. Pending the user's protocol decision, retaining this existing controller does not create a new controller lifetime. CPU ticks may still incur charges; this audit did not reconcile billing or establish a zero-cost remainder.

No campaign GPU workloads remain. Billing reconciliation across setup attempts and training remains a separate pending handoff. No scientific comparison or reserved-population result is reported here.

The reviewer made only bounded local CPU reads/checks and read-only remote queries. No campaign artifact, shared source, journal, remote app, Dict or volume was changed. No workload invocation, deployment, stop, commit or push occurred.
