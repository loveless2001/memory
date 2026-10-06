# P2C prereg v0.2 independent audit — PASS

Reviewed `0c8d35839be2c91e7dc406e128be8c3f9be58e36`, prereg SHA256
`b1bafbbdeca4668d8bd9270f54a970576332a6612c1bc81a55a5d705ab031413`.
The working document is byte-identical to the committed version. Changes
since closed P2G `e5a991a` affect this prereg only.

All four v0.1 audit items are resolved:

1. Recipe/distribution contrast and mechanism hypotheses are distinguished;
   episode length, exposure, positions, stream draws and compute limitations
   are explicit. P2G's N16 seed-1 +8.50pp is retained.
2. Implementation/preflight, actual training authorization and registered
   readings are separate gates. Four validated cells and successful parity
   precede one reserved population run. Endpoint and stop rules are fixed.
3. Exact input/index and start/end identities, complete parity files, E=on
   registered corners and E=off legacy fixtures are specified. The schedule
   preserves model/optimizer/generator across the transition and uses the
   unchanged full-filler evaluation distribution.
4. Reference prerequisite is measured on E=on fresh rows, never preset;
   support is per N and the full-filler development curve is descriptive.

The accepted design is fixed: update indices 0–999 with filler length 0,
1000–1499 with length 40, final registered endpoint after 1500 updates;
N32/N64, seeds 0/1, exactly four new cells. All eight reused checkpoint
manifest/parameter bindings and eight saved parity hashes remain unchanged
from the v0.1 checks. This does not substitute for runtime parity.

Reservation remains **$11.12716980** under the **requested $12** cap using
the frozen guard policy. No cap approval is inferred from prereg clearance.

**Clearance: implementation and bounded CPU preflights may proceed.**
Actual 1500-step training requires the implementation audit and the user's
scoped approval specified in the prereg; reserved readings follow its gates.

Implementation interpretation to retain in code review: `gain_label` is the
classifier's string; the table's `gain` flag is exactly
`gain_label == "reproducible gain"`. Loss, exclusion and neither must all
reach the no-gain branch. "Only the final state ... is evaluated" denotes
the registered endpoint; the separately specified full-filler development
evaluations remain descriptive and cannot select a checkpoint or schedule.

Evidence: `codex-261006-p2c-prereg-v02-checks.json`, SHA256
`d49ab27daf923e947c9545818c1ef0a9b05c781986fac1e561657f1a392b6670`.
No runtime/code/prereg edits, models evaluated, training cells started,
reserved-seed uses, or paid work in this audit.
