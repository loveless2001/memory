# Attempt-2 repair/reset draft review — gravity 21633

**Draft review only; final committed package/index verification remains pending.** No remote mutation was performed. HEAD remained at the previously cleared `89df08f` while Claude prepared the repair and ran its full suite.

Independent relevant tests passed: **36 passed in 7.18 s**, covering the slot runner, build-context guard, controller namespace agreement and prior lifecycle fixes. [Test log](independent-draft-tests.log). The prior independent [build-context reproduction](../codex-261007-p2p5-pk-21629-launch-hold-audit/build-import-preview-probes.json) already showed the old import failure and the provisional repair's correct local/remote refusal behavior.

The draft manifest retains the same analysis section and memsub binding. Exactly four launch entries change: the three runners and execution supplement. [Snapshot details](draft-review.json). The frozen numerical implementation, registered population and v6 price model remain unchanged.

The new `-r2` controller guard/registry names agree across controller, slot and readings runners. Original controller Dicts and attempt-1 evidence are preserved. The supplied read-only Dict listing contains only the old campaign control Dicts, with no new `-r2` or slot/readings guard/admission Dicts. Final pre-launch checks must use the frozen package and current state.

**Pre-deploying the readings app is technically compatible with the protocol.** The GPU function has no schedule or warm minimum; deployment does not invoke it. The unchanged admission guard, slot-validation precondition and analysis binding still control the one readings call. Pre-deploying all ten GPU-app images before controller deployment/arm removes image-build delay from its spawn window. Image builds can incur CPU charges even though no GPU call is spawned.

Draft feedback sent in gravity 21635:

- Supplement step 7 must refer to validation step 6, rather than step 5.
- State the exact 18-cell matrix in the user handoff: 16 trained cells from four arms at N16/N32 and seeds 0/1, plus two oracle N32 cells; oracle N16 is transfer evaluation of those checkpoints. The earlier five-arms-by-two-Ns wording implied 20 training cells.
- Keep the $0.00004958 attempt-1 controller snapshot explicitly partial and failed-build billing unresolved. Separate the extra attempt-1 controller/build allowance from the eleven planned attempt-2 builds. An explicit allocation from the existing margin can preserve the same $259.99 conditional reserve without double counting.

The owner is still finalizing tests, commit and index. These draft checks do not clear a paid retry/reset, overwrite a consumed guard or authorize deployment. No source, journal, remote Dict, volume path or proof artifact was edited by this review.
