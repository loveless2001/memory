# P2G final implementation/preflight clearance

**PASS — implementation and CPU preflight gate cleared.** All recorded code blockers are resolved, and the final r3 package independently verifies against the reviewed source. This clears the technical gate for the registered six-cell experiment; it does not grant user training or spend authorization.

Reviewed implementation: `07261613b206087dcddc50a1ed74ec5925ddb708`.
Final evidence commit: `37d82f5d1073be8b37ace7a5542cf1ee503ead41`.
Prereg v0.2: `25fdbc5`, SHA256 `c2fa7394e9e621766af705743d46715b9584c83e161a90bdfd45d928908925c3`.
MCP request: #gravity 21335; verification acknowledgement 21337.

## Final evidence verified

- **6/6 r3 parity files parsed-equal and byte-equal** to their frozen references: 5,120 rows each, 30,720 total. Schema, correct flags, five legacy interventions, 256 shared episodes per intervention, and four unique queries per episode all check out.
- Every output is byte-identical to r1/r2; step-0 telemetry is identical across all three packages.
- Start/end observer identities are equal and bind to implementation `0726161`. Every recorded analysis/index/grid hash matches that producer commit and the current checkout.
- Current memsub source SHA256: `5c3b5420152de933a04264604fdc1fb6312a24609b631ad9fd0c614755bde6a2`.
- The only analysis hash change from r2 is the reviewed recovery validator fix. All six reused checkpoint manifest/parameter/config/source/group identities remain valid.
- Final preflight report SHA256: `2f2ddfc63f68745a2708181b87ada8fbdb64d20ee89ee380cd4ecc374b3cb6fd`.
- Independent verification artifact: `plans/reports/codex-261006-p2g-preflight-r3-independent-checks.json`, SHA256 `c90d332131b2712bfa85ac2dc2900d3fca2fd1910abb728cbe25ff4e788233be`.
- Previous independent regression results remain applicable: 62 focused P2G tests passed after the three original fixes; 29 recovery/grid tests passed after the final CLI fix. No executed code changed when the r3 evidence was committed, so those tests were not repeated.

## Reviewed execution scope

Exactly the six new cells in group `p2g-selective-write-v1`, each with fixed 1,500 steps:

| cell | timeout seconds |
|---|---:|
| gateclosed-learned-n16-s0 | 6106 |
| gateclosed-learned-n16-s1 | 4640 |
| gateclosed-learned-n32-s0 | 8773 |
| gateclosed-learned-n32-s1 | 6952 |
| filleroff-learned-n32-s0 | 8773 |
| filleroff-learned-n32-s1 | 6952 |

Reviewed reservation: **$12.32978160**. Proposed scoped cap: **$13**, currently unapproved. `P2G_CAP_USD=None`; ordinary launch planning was independently confirmed to refuse a missing cap.

Training-artifact evaluation is restricted to the published `9_300_011+s` population. The reserved `9_400_011+s` population is used only in one registered readings run after all six cells validate. Preserve attempt/claim limits, exact group/coverage, saved call IDs, deadlines, and verified shutdown. No automatic retries or expansion are cleared.

The controlling authorization gate is prereg `Gates` item 2: "Implementation audit (codex) + user's scoped training authorization with the reviewed cap". It also requires authorization for local execution. User 21289 authorized drafting only; the latest request to read #gravity is not a scoped training approval.

After an explicit scoped user decision, review the proposed cap-binding change against this cleared implementation before launch. A one-line cap binding does not by itself authorize a different experiment or change the observer/analysis protocol. No deployment, training, paid run, local training, fresh-population evaluation, or duplicate parity job was started by this audit.

The evidence remains limited to the registered tiny random backbone synthetic recipe. Preflight agreement and initialization telemetry are engineering evidence, not a trained selective-write result, scaling result, pretrained-model result, or P3 claim.
