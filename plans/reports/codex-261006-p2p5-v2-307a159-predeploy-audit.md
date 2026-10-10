# Re-timing v2: baseline accepted, sampler cleanup repair required

User gravity 21501 authorizes option A, the four-configuration re-timing under a
fresh `$3` envelope separate from the development tests. No extra user permission
is required for that scoped run once its concrete runner is technically cleared.
Commit `307a159` is not yet cleared to deploy because the optional sampler cleanup
can raise after a successful child run and before the exit artifact/volume commit.

Independent CPU checks establish that v2 runner SHA
`38b5f4b8e14c829aab779f9bee27b045655081b4f9454009b779123faa8a4c1a`
retains the accepted v1 lifecycle, admission, source binding, image-build function,
validator, producer and collector function bodies. The new group/app/guard names
and derived attempts Dict avoid v1 collisions. Profile script
`b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c`,
shared logic `32bb3a3a38bf375e4c9107e4b3d7dc4c6392076cb5ba55f7c599fab644329e6c`
and v1 runner `6406e6415def0e28ccccbd67c0a424a5c052329c914c49828661bd89cf594e28`
remain byte-identical. Candidate memsub is the parity-tested
`b87a767baac578d94a6f778560f4fb451fd60679cca48412218adaac74f74085`.

The two targeted profile/reaper suites independently pass **75 tests in 0.55 s**.
Actual SDK resource fields and image graphs preserve hard GPU-worker CPU/RAM
tuples and the shared-logic mounts for both worker and CPU reaper. An isolated
copy imports without the shared logic, executes the actual build function under
pip/download substitutes, then requires its runtime shared mount. Supplying the
unchanged logic exercises bound whole-app stop before optional call cancellation.
These are local checks, not a fresh paid build or remote reaper proof. The accepted
historical remote proof still covers the unchanged shared stop machinery.

The reservation exactly reproduces v1: GPU lifetime `$1.9563936`, reaper
`$0.009647`, full build allowance `$0.168384`, margin `$0.25`, total
**`$2.3844246` within `$3`**. It retains the declared scheduling, stop-latency
and build-overuse assumptions; it is not a platform-enforced cash limit. No
previous development reserve is transferred or silently released.

New failure counterexample: substitute a sampler whose initial wait times out
and whose kill raises `ProcessLookupError` because it disappeared in the race.
The actual `stop_gpu_sampler()` propagates that exception. Since this call is in
`run_profile`'s `finally`, execution does not reach exit.json or artifacts.commit.
The missing-command start-failure test does not cover this path.

Contain all terminate/wait/kill/final-wait errors, add a bounded reap after kill
when possible, and record accurate status/errors/returncode without declaring a
still-unreaped rc=None process stopped. Preserve the valid child profile regardless
of diagnostic cleanup failure. Add meaningful timeout/kill-race/error fixtures and
freeze the repaired source before deployment. Record query, cadence, start/end
epochs and timezone so CSV samples can be attributed to progress windows without
changing the profile's timing hooks.

The sampler remains descriptive. NVIDIA defines utilization.gpu as the fraction
of a recent sampling window with at least one executing kernel; the window is
product-dependent, approximately one sixth of a second to one second. Inference:
this measures activity over time, rather than spatial SM occupancy or available
capacity for another experiment. Low readings alone cannot establish concurrent
fit, throughput or cost savings. See the [official NVIDIA SMI documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html#utilization).

The four re-timed shapes will provide measured update/dev timings and peak memory
for the specified arms/N32/seed99. They cannot supply a verified full-campaign
price or worst-case bound for unmeasured controls/N16, final-evaluation workload,
I/O and app topology. Preserve the original ledger; any new ledger must name those
assumptions and the artifact-evaluation 52/20-batch workload correction. Numerical
parity compared gradients, not separately exported correction tensors.

Evidence:
`codex-261006-p2p5-v2-307a159-baseline-check.py/.json`,
`codex-261006-p2p5-v2-307a159-targeted-tests.log`, and
`codex-261006-p2p5-v2-307a159-sampler-counterexample.json`.
The earlier `...307a159-tests.log` records a mistyped nonexistent test-file argument
and no executed tests; the correctly named targeted suite above supplies the
actual 75-test result. No deployment, remote proof, paid invocation, commit, push,
implementation edit or historical artifact mutation occurred in this audit.
