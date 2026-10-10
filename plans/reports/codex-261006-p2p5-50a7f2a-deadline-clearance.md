# P2.5 profile deadline and cleanup closure

Reviewed `50a7f2a0b6c70474d22c46a407761b1605ac5df7` on 2026-10-06 in response
to #gravity 21443. **The specific hard-deadline and watchdog-cleanup HOLDs
are CLOSED at this source.** This is profile-control clearance, not a GPU
fit, throughput, learning, complete implementation, or paid-launch clearance.

The profile script is bound to SHA256
`b5b0746a40afbd7c9feb2bcf7aa6967189903673829cf2a8d4a2afc25237a08c`.
The independent guard remains unchanged at
`52c0ec5ec873fa4cfafe82f1fa612c71969e64e184b6bd557665e9b55f7f3054`.
Source inspection confirms that all work after watchdog construction runs
inside `try/finally: watchdog.cancel()`, including setup, the configuration
loop/cache cleanup, and report/progress writes. The commit otherwise adds
only Claude's exception probe and its retained result.

Independent evidence is in `codex-261006-p2p5-50a7f2a-deadline-checks.py`,
its adjacent JSON, and `codex-261006-p2p5-50a7f2a-deadline-fixtures/`.
**Nine CPU-only subprocess probes passed** against the actual main and
profile-config paths, using inert CUDA calls and substituted workloads:

- Stalls inside load/train and evaluation: real watchdog SIGKILL, exit -9,
  durable partial progress, no surviving helper. Each fixture substituted
  an 8s GIL-holding C sleep and a 0.5s watchdog.
- Successful matrix: exit 0, all four configuration summaries, 40 completed
  updates, four dev-eval completions and the end record; helper cancelled.
- First OOM and first training error: exit 1, no later configuration,
  terminal error evidence retained; helper cancelled.
- Environment setup, initial progress write, final report write and final
  progress write exceptions: exit 1, no surviving helper. Earlier progress
  survives where writing was possible.

The source/hash bindings and original OOM artifact/log hashes stayed equal
throughout the probes. No model load, real training/evaluation, CUDA work,
artifact/reserved population use, laptop retry, or paid execution occurred.
The previous 11 CPU model/fingerprint tests remain the earlier checkpoint
evidence; they were not needlessly repeated for this control-flow-only fix.

Historical audit scripts now refuse a changed profile hash before running
their probes, so a stale harness cannot accidentally execute the revised
watchdog implementation. Their retained result JSON and historical findings
are unchanged; current clearance is recorded here.

For a future concrete launch, capture the process exit status externally
and enforce the outer timeout. One injected final-progress-write error
leaves a completed `profile.json` but exits 1, so that JSON alone must not be
treated as successful execution. These are launcher requirements, not a
new defect in this corrected cancellation path.

The paid-profile runner and complete charge ledger remain undrafted and
unaudited, and prereg Gate 2 still requires explicit scoped user approval.
The original OOM supplies no measured throughput or full-run cost. The
implementation/readings protocol and registered-cell launch are outside
this narrow closure.
