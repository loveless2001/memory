# P2C final technical gate — CLEARED

Implementation `8c3161ac90fda21ff1d767a392af2ed08f802ec5`, evidence
`ada6312b859be481911a829c563d58cac14d719d`, prereg v0.2 `0c8d358`.
The implementation source audit and completed CPU preflight gate pass.
This is technical clearance; the requested training cap is not approved.

Independent read-only verification of committed preflight r2:

- Eight complete legacy fixtures, 5120 rows each, independently parsed and
  byte-equal to their bound references. All 40,960 rows have the expected
  five interventions, 256 episodes and four queries, valid schema and
  correctness flags, and identical targets across interventions. P-on
  covers v2 N32/N64 s0/s1; P-off covers P2D N16 and P2G N32 s0/s1.
- All ten reused manifests/configs/parameters/source/group bindings match.
  Start/end observer identities are identical at 8c3161a. Actual prereg
  bytes, index, grid, live memsub and every analysis file match their
  recorded hashes and producer commits. The prior two findings are fixed.
- Schedule smoke records training lengths [0,0,40,40], evaluation length
  40 and the scheduled diagnostic label. The previously independently
  checked schedule/model/optimizer/generator and default-regression
  contracts remain unchanged.
- The committed full-suite record is verified: 206 passed, exit status 0,
  at the full 8c3161a identity. The original r1-aborted log remains an
  aborted attempt and is not counted as passing evidence.

Preflight report SHA256:
`21b0c88fb33a92ead7e0efb3ea3122e055ad8f7310171e0b957715250ddb52c2`.
Independent verifier output SHA256:
`0b394b87671c8fd01d4b25767bbd3a79076e6ed649db03fd28eeacdd2d18f6eb`.
Verifier and output:
`codex-261006-p2c-preflight-r2-independent-check.py` and
`codex-261006-p2c-preflight-r2-independent-checks.json`.

The concrete reviewed execution scope is exactly four new 1500-update
curriculum cells, N32/N64 × seeds 0/1, group p2c-filler-curriculum-v1.
Updates 0–999 use filler length 0; 1000–1499 use 40, writes on throughout.
Artifact evaluations use 9_300_011+s. All four validate and parity passes
before one registered readings run on 9_500_011+s, then independent results
audit. No schedule selection, automatic training retry or expansion.

Independent own-v2 deadlines are 8773/6952/11797/10809 seconds, reservation
**$11.12716980** under the **requested $12 cap**. The scoped runner's
approved cap remains None; the prereg's user approval is the remaining
gate for training. Implementation/preflight clearance does not extend to
P3, pretrained models, scaling, or an address-learning mechanism claim.

No duplicate parity job, checkpoint evaluation, registered training cell,
reserved-population use or paid call was performed by this final audit.
