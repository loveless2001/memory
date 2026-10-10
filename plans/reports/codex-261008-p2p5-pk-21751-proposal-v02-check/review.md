# Proposal v0.2 follow-up

Frozen proposal 14e2b43 matches SHA256 `f13f5a712b10b997a6ea3f0cb07b32c34a6e625ee4c7ed14ec797345dc49c9de`. The prior schema/null, runner isolation, recovery declaration and smoke-bound corrections are incorporated. Local CPU implementation clearance stands. This is not implementation or model-smoke clearance.

The in-app reaper is a changed execution arrangement. Its shared helper bytes match the retained CPU self-stop proof, whose report and post-hoc stopped verification pass. That evidence establishes the observed historical stop path, not validation of the new probe's bindings, guard states or latency bound.

Concrete implementation requirements identified with in-memory examples only:

- `reap_decision` accepts NaN and infinity as numeric deadlines and then never reaches either deadline stopping or abandonment fallback. It also accepts boolean True as a deadline. Validate a finite, positive, non-boolean deadline and give unarmed/malformed guards a bounded fallback in the probe adapter. Refuse GPU admission for malformed/unbound guards.
- `reap_and_stop` delegates to its stopper with a None app id when the guard lacks one. The shared stopper then permits a name-only stop. Bind/check the probe app id before delegating deadline or abandonment stopping, and test mismatched/missing ids without risking another app. Preserve the shared historical file.
- Cover interrupted guard binding, abandoned deployment, stop errors/hangs and actual image/guard/app/resource bindings in the implementation tests. The 120-second schedule and 240-second stop tail are operational assumptions, not a latency bound established by the earlier 60-second CPU proof.

At the stated rate and allowances the nominal arithmetic is $40.597864912. The revised approximately $41 planning reserve is consistent with those inputs; it remains conditional on the ledger's eventual resource, setup, startup, reaper and stop-tail accounting and is not an approved cap. No price refresh or remote billing query was performed in this follow-up.

The opening launch-order sentence still places local smoke before implementation audit; fix it to match the corrected body: frozen implementation/CPU tests → independent review → bounded model smoke → smoke/ledger audit → explicit paid cap. This is an editorial correction during local implementation, not another proposal-only approval loop.

Evidence: `check-plan.py` and `evidence.json`. Work used static local files and fake in-memory stores/stoppers only. No model construction/forward, population generation, GPU or Modal call; no owner/campaign file edits.
