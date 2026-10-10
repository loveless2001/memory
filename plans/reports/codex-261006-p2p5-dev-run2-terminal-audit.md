# P2.5 option-A run 2: bounded GPU numerical parity accepted

Run 2 is accepted as a complete six-case numerical-parity check on the reviewed
Qwen/L40S development path. All eight evidence files match their committed bytes
at `c17cfcc`. The actual stdout and returned parity report agree. Child exit and
console exit are zero; outcome is `ok`; remote wall is 400.373 s and client wall
406.701 s.

All six registered development cases at N32, seed 99 and two training updates
pass at rtol `1e-5`: learned/b16 with training filler 0 and 40; oracle,
single_cell, random_fixed and memory_off/b4 with filler 40. The checker reports
656 loss/gradient/final-weight comparison rows, each with zero absolute and
relative difference, zero structural problems and identical dev predictions.
Its separately enforced initial-weight equality also passes. The report's
`bitwise` flag is true for each case. This is the checker's scoped tensor-equality
evidence, not an all-output or mathematical-equivalence proof.

Reference source hash is
`048df6402d9ee52f04228f736e4c40d31c9ed527bb7d868c9c12b49d388f5eb6`;
candidate source hash is
`b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085`.
The deliberate delta perturbation is detected: failed comparison, max relative
difference `0.9908984654940161`, at `final/adapters.13.beta_proj.bias`.
Namespace isolation passes with 21 reference modules, 23 candidate modules,
no leaks, and file paths under their respective mounted/copy locations.

The launch identity remains `1306f26`. The later checker docstring correction at
`0f5932d` has the same executable AST after removing only the module docstring.
Original checker hash is `b384c103...`; documentation-source hash is
`a8969478...`. No later hash is retroactively asserted as the remotely mounted
script. Raw tensors were not retained for a second offline gradient/weight
comparison: this independent audit validates the previously reviewed checker,
source binding, complete report, negative control, namespace isolation, stdout
agreement and terminal state.

Read-only verification completed at **2026-10-06 13:29:32 UTC**. Both option-A
apps (`ap-E2KdNOH6Vb0qjnJTVdKz4U`, `ap-UUv74AxrTl2LhmY6g128Jk`) are stopped,
with zero tasks, zero matching containers and recorded lifecycle stop timestamps.
This does not establish shutdown of unrelated workspace applications.

The current app-only reported usage snapshot is `$0.21822959` for run 2 and
`$0.53878894` for run 1, totaling **`$0.75701853`**. This is not a settled invoice
or verified total build cost. The absence of a `Building image` console line is
consistent with cached reuse but does not independently prove zero build charge.
Keep the full `$1.55 + $1.18 = $2.73` reservations booked within the authorized
`$3` development envelope until billing is reconciled. No new paid work is
authorized by this result review.

The user-facing speed and campaign-price statements in gravity 21498 need
correction. Exact ratios from the artifact are:

| Case | Reference train_s | Candidate train_s | Aggregate ratio |
|---|---:|---:|---:|
| learned/b16, filler 0 | 33.432 | 19.695 | 1.697 |
| learned/b16, filler 40 | 45.076 | 29.332 | 1.537 |
| oracle/b4, filler 40 | 26.337 | 23.824 | 1.106 |
| single_cell/b4, filler 40 | 24.096 | 22.092 | 1.091 |
| random_fixed/b4, filler 40 | 27.935 | 23.886 | 1.169 |
| memory_off/b4, filler 40 | 8.265 | 8.475 | 0.975 |

These aggregate durations include model construction, first-update warmup and
CPU loss/gradient capture. Reference always runs before candidate. They are
development signals, not measured training-step speed ratios or registered
retiming. The stated `1.7–1.9x` range does not match these observed ratios.
They do not justify the projected `$125` campaign cost or `$215` worst case;
the earlier `$365` ledger was itself not a validated upper bound. A measured
new cost ledger must bind the actual campaign workload, all relevant controls
and N16 assumptions, final-evaluation workload, I/O and lifecycle costs.

The six-case check does not separately compare correction outputs or training
telemetry, and other dev numeric fields are not pass-gated. It does not establish
full-campaign behavior, GPU checkpoint/resume or campaign-runner integration.
The previously checked save/resume proof remains a tiny CPU fixture. Language
about no mathematical changes should be limited to the observed equality in
these bounded cases.

Likewise, these measurements do not establish that the GPU is idle or that
running two or three jobs on a larger GPU will halve cost. That requires actual
utilization, peak-memory and contention measurements, price arithmetic and its
own scoped plan. No concurrency experiment or further paid test was launched.
Registered retiming remains a separate user choice with a concrete reviewed
runner, workload and budget before launch.

Evidence: `codex-261006-p2p5-dev-run2-terminal-check.py` and its `.json`, alongside
the preserved c17cfcc artifacts. Original experiment evidence and implementation
files were not modified by this audit.
