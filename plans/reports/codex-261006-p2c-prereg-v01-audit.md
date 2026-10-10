# P2C prereg v0.1 independent audit

Reviewed `5271a50980b949c6bd767f4a0eeb628c2554f508`, prereg SHA256
`2edf04a6dd5f8f470feb57245812daec4326fceb21ac992a83189f179fbbdda6`.
Status: **design choices accepted; prereg clearance held for revisions below**.
This audit performed no training, checkpoint evaluation, or reserved-seed use.

## Accepted choices

- Freeze the 1000/500 schedule. It is a defensible pilot allocation, without
  evidence that it is optimal. Use update indices 0–999 and 1000–1499, retain
  the same model/head/optimizer and continuous training generator at the
  boundary, and evaluate only the final state after 1500 optimizer updates.
- Retain N32 and N64, both seeds. N32 checks the load with a demonstrated
  filler-off recipe gain; N64 checks a higher load where that historical
  comparison failed. Results remain separate per N; do not drop N64 after
  seeing N32 or infer scaling from either outcome.
- The five-row decision table is total for valid inputs. The inherited
  classifier has ordered gain/loss/exclusion/neither labels, and half is
  unavailable unless the measured reference contrast is a reproducible gain.
  Keep all per-seed intervals, labels, memory tests, and half intervals even
  when a headline conjunction fails.

## Required prereg revisions

1. **Mechanism scope and retained P2G effects.** Motivation says the
   interference/address-learning hypothesis is "tested here", but the limits
   correctly say there is no address-learning test. State that this pilot
   tests the curriculum-versus-v2 recipe contrast; interference and address
   learning are possible explanations, not confirmed or excluded mechanisms.
   A positive result is compatible with changing episode length, token
   exposure, positions and training-stream draws. Same optimizer-update
   count does not equal the same token or compute budget. Also retain P2G's
   N16 seed-1 evaluation-off gain (+8.50pp); the N32 >=5pp exclusion does not
   describe every historical v2 evaluation contrast.
2. **Explicit execution gates and stop conditions.** Clearance permits
   implementation and bounded CPU tests/parity/schedule smoke only. Four
   actual 1500-step cells, on Modal or locally, require implementation audit
   plus fresh user approval of the exact proposed $12 cap/ledger. Permit
   exactly one reserved-seed readings run only after all four cells validate
   and all parity gates pass. No early stop, checkpoint selection, automatic
   training retry, schedule tuning, missing-seed headline, or expansion.
   A failed cell, artifact validation or parity gate stops the planned
   readings; repair/resume needs its own reviewed scope.
3. **Bindings and parity boundaries.** Commit the exact reused manifests,
   configs, parameters and complete parity references/hashes in the new
   index before evaluation. Bind grid, prereg, observer, rules, runner and
   source at start and end, and abort on changed inputs or unmatched episode
   hashes. Parity uses the complete five-intervention legacy files (5120
   rows each); the new readings use three interventions (3072 rows each).
   "E=on everywhere/no write mask anywhere" applies to the registered
   readings and curriculum training, while P-off compatibility fixtures
   intentionally exercise the old E=off path. The default empty schedule
   must preserve initialization, train-stream draws, updates and evaluation
   behavior; scheduled training must keep every dev/artifact/reading
   evaluation at filler_len=40, E=on.
4. **No preset reference label or joint claim.** Historical N64 P2D was an
   E=off comparison; P2C's reference is E=on on a new population. Its half
   status must be computed from that measured prerequisite, including a
   possible reproducible gain. Describe the question/readings as per N;
   any claim of support at both loads requires both per-N support readings.
   The full-filler dev curve measures transfer to full-filler episodes
   during each phase; absence of accuracy there cannot establish failure to
   learn in the no-filler training distribution. It is descriptive and
   cannot select the phase boundary, endpoint or schedule.

## Artifact and ledger checks

Saved-fixture checks PASS; no models evaluated. Eight reused checkpoint
parameter hashes match their own manifests and roles: v2 N32/N64 s0/s1,
P2G filleroff N32 s0/s1, P2D filleroff N64 s0 and top-up N64 s1. Eight
complete parity files exist with 5120 rows each: four v2 P-on, two P2D N16
P-off and two P2G N32 P-off. This verifies saved inputs, not runtime parity.

Using the frozen repository guard rates/margins and each cell's exact own
v2 wall, independently derived timeouts are 8773, 6952, 11797, 10809 seconds.
The 3x nonpreemptible reservation is **$11.12716980**, under the requested
$12 cap: training $8.06790888; startup/teardown $0.30309120; refused replay
allowance $0.35360640; CPU-overuse $0.60256332; image $0.30; fixed $1.50.
The replay allowance bounds refused duplicate invocations; it does not
authorize another training attempt. An expected $4 is an estimate, not a
spend bound. Launch must use the new group's exact dry-run and identity.

Machine-readable evidence: `codex-261006-p2c-prereg-v01-checks.json`, SHA256
`020719f32306dc1371f458b36a1e645eec03426c26dd575a82970cabc2292112`.
No code or prereg edits by this reviewer; no paid work authorized by this
audit. A revised, committed prereg is needed for implementation clearance.
