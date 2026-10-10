# Independent design clearance: Amendment PK v0.4

Reviewed 2026-10-06, commit `0578975`, amendment SHA256
`8c829c1172aac787d83f103d876926c27425fb755f93a98cf514dab52d99aa56`.

**Cleared to proceed with the already-authorized free implementation and meaningful CPU tests.** The four
focused issues from review 21556 are addressed at the design level. This clears the amendment-to-implementation
gate only. It does not establish implemented durability, successful GPU resume, a campaign price/bound, or
scientific results. No GPU proof or campaign execution approval is conveyed.

| Issue from 21556 | v0.4 change | Disposition |
| --- | --- | --- |
| Check-then-write ownership race and missing initial state | Writes confined to an admitted epoch's directory; acknowledged inheritance and exact predecessor binding select the authoritative chain; acknowledge-before-work and declared NEW-by-recovery policy; stale-publication interleaving test; FAILED committed before proof D's fault | Sufficient protocol direction for implementation audit |
| Physical replay versus fixed training endpoint | Exactly 1500 logical updates along the selected chain, physical/replayed/stale work recorded separately; eight logical updates for proof; eval-only recovery adds zero updates | Resolved in the design |
| Timing fields and unstable-reference tolerance branch | Scientific schema excludes clocks/provenance from numerical equivalence; explicit N/A and strict field/name/shape rules; A′ must pass the tolerance/control test before the tolerance branch | Resolved in the design |
| Restarted evaluation work omitted from price | Restart allowance includes model load, checkpoint reload, C plus in-flight work and one full evaluation attempt; commit/serialization overhead; explicit proof evaluation counts | Resolved at planning level; arithmetic awaits actual implementation/timing |

Bindings were independently checked: working amendment bytes equal the committed bytes; this commit changes only
the amendment; the tracked worktree was clean at the check. Original prereg and grid hashes remain
`0ce61a096b0c7150e00f0a604ed85cb8f9694584cb70790d43d5fb3d010c2002` and
`d1c045eadfb562829cab72f58ba6b293f573f2e853629d3a3dd324b740a13073`.
The registered universe still has 18 distinct cell ids in nine fixed arm/N pairs with seeds 0/1. The timing
design has 18 configurations (nine pairs times two phases), with oracle N32 only. Proof artifact evaluation
counts are 7 for learned/random_fixed/oracle, 6 for single_cell, and 3 for memory_off, including the two-batch
train-split minimum. All six inputs to the historical L40S correction supplement were also hash-checked unchanged.
These checks are retained in `codex-261006-p2p5-pk-0578975-draft-checks.json` beside this report.

Implementation review must now verify the protocol in the actual runner, supervisor and consumer, rather than
accepting this source review as evidence of execution. In particular:

- Make the selector bind exact immutable predecessor generation/hash records; an older epoch's later mutable
  state must never alter a newer epoch's inherited chain. Cover a late old publication after handoff, an
  unacknowledged newest admission, commit/ack interruption, and inherited FAILED/LOST/COMPLETE precedence with
  meaningful CPU interleaving/failure tests. Treat acknowledgements as a concrete durable protocol, not as
  evidence inferred merely from a locally renamed file. Admission/start bounds and deadlines must fail closed.
- Test the terminal generation and eval-only consumer through the actual training/run_pilot hooks. Check logical
  update continuity and preserved attempts. Abrupt loss may leave a physical-work tail unobserved; retain observed
  records and label the missing tail with its explicit bound rather than inventing an exact durable count.
- Implement the frozen comparison scope with strict expected keys, parameter names/shapes, predictions and
  logical update ids. Timing values receive finite/nonnegative/deadline checks; hosts and other provenance ids
  receive type/identity/binding checks rather than numerical finiteness tests. Exercise unstable A′, missing/extra
  fields, NaN/inf, shape and N/A mismatches as rejection cases.
- Preserve run_pilot's existing population defaults. Bind the separate proof grid, proof-only populations, fault
  injection, exact timing/evaluation multiplicities and resource/restart settings in the implementation package.
  No registered training or reserved readings are consumed by CPU preparation or proof mode.

Next handoff: implementation commit/source hashes, runner and proof-grid paths, CPU results/artifacts, and a
complete charged proof reservation including every admitted container start, startup/model loads, timing
configurations, commits, teardown, build, reaper and margin. The approximate $2 proof target remains a target.
The implementation audit and separate user proof-cap approval precede any GPU proof. Only an audited proof
PASS permits the schedule-bound A100 campaign ledger, followed by explicit campaign-cap approval and launch audit.
The single reserved readings run remains after validation of every registered cell.

The old-model correction ($160.43 estimate / $273.79 reserve) remains a reference to the historical single-process
L40S assumptions. It is not the packed A100 estimate. This review creates only new report files; no historical
preregistration, grid, ledger, evidence, controller journal or implementation bytes were changed by the reviewer.
