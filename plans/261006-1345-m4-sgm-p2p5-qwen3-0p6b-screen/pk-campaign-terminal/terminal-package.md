# P2.5 PK campaign: terminal package (for codex final artifact audit, codex 21718/21730)

Status: campaign TERMINAL. All 11 attempt-2 apps stopped and verified: 9 slots, readings, and the controller (stopped
by bound id at 17:50:07Z). The final billing is pending.
Readings report posted claude 21729. Authority: user 21627 (campaign, $259.99 conditional reserve), user 21710 (option B).

## Outcome
- ORIGINAL reading (prereg + supplement step 6, kept at BOTH N): `unavailable: learned-n32-s1: state FAILED`.
- POST-HOC AMENDED readings (`campaign_label` and every per-N `label` = "post-hoc amended"):
  - N32: `screen not passed`; memory_off=neither, single_cell / random_fixed = positive gain >=5pp excluded;
    memory_use false; read-address use established.
  - N16: `screen not passed`; all three controls = positive gain >=5pp excluded; memory_use false;
    read-address use not established.
- Amendment dependence: a pass needs gain over every control on both seeds. learned-n32-s0 alone is below
  random_fixed (CI hi -3.6pp), so no s1 value could produce a pass. The N16 reading does not use learned-n32-s1.

## Readings run
- Exactly one call fc-01M4BG37XCKFD3A9WRJ91D44MB (spawned 15:35:44Z, admission start-1 only), rc 0.
- Identity == expected: memsub 2eee4228…, manifest 882dd4a4…. end_binding "verified". Reserved seed base 9_600_011.
- App ap-MvPw7JVom3vnRTxVVyzldN stopped 17:42:47Z, verified 0 tasks / 0 containers (`collect_status.json`).
- 20 row files: every sha256 equals its `rows_sha256` in readings.json (checked locally).

| file (under `p2p5-qwen3-0p6b-screen-v1/readings/`) | sha256 |
|---|---|
| volume-evidence/collect-1/readings-v1/readings.json | e8764c427dd8bfc63098adc5de8f6499ef2f8ced679cbd192c77f36fadb4dfda |
| volume-evidence/collect-1/readings-v1.exit.json | 80a632adfe6291e68758f0c1d3dba15304e524d1fb70a8d13cdc59128d3dabf5 |
| collect_status.json | ba3a5f42ebec0c8627a023725f7a4878efc7dbf0695a5c59eb758857766b1ed8 |
| launch_provenance.json | 85932ec514725626bbbe195661fa2637d9cff6ee9d481fc9c4650b782b152424 |
| call.json | f591e756e50e163551d481e94f54107f7970800ceaf789bc668fb33799537572 |

## Slots (attempt 2)
All 9 `poll=result`, `final_shutdown=stopped_verified` (per-slot `collect_status.json`). 17/18 cells COMPLETE valid;
learned-n32-s1 FAILED (original record bytes unchanged; spec state d4996651…). Slot loop: "ALL 9 SLOTS FINAL" 13:40:27Z.

## Controller
ap-suOdTgdc8PNSfZ3jbnsesa (-r2) was STOPPED BY BOUND ID at 17:50:07Z (codex 21731 terminal cleanup), before its
write-once deadline 1791408417.25 (21:26:57Z). Verified: stopped, 0 tasks, 0 containers. The -r2 Dicts were
only read, not reset: guard, 10-app registry and 332 ticks are exported. Evidence: `../pk-campaign-launch/attempt-2/98-*`
(script, start time, bound-verified json, exit 0, stderr). An independent check of all 12 campaign app ids
(`99-app-list/99-container-list-after-controller-stop.json`): readings and control are stopped with 0 tasks; the other
10 are unlisted; 0 campaign containers. No memsub app is in any non-stopped state.

## Billing (PRELIMINARY: `billing-reconciliation-prelim.json`)
App-attributed, 2026-10-07 00:00Z through the 17:00Z hour (that hour was still open):
- slots $119.27
- readings $7.09
- controller(s) $0.08
- total **$126.44**

For reference: v6 estimate $116.31; conditional reserve $259.99, of which readings $16.71. Attempt 1: controller
$0.00005; the failed slot image build is not app-attributed. learned-n32's 06:00Z hour may include the attempt-1
deploy (same app id). The $8.57 proof hold is separate (Oct 6). FINAL: re-fetch at 19:15Z, after the 17:00Z hour closes.

## In git / not in git
- Committed: the attempt-2 launch logs (50–94, collect loops), the readings dir, and the per-slot non-binary volume
  evidence (state/done/metrics/telemetry/requests/acks, per_example jsonl). That is ~30 MB, the same practice as the proof.
- NOT committed: 558 checkpoints / safetensors (12.4 GB). They are bound by `SHA256SUMS-excluded-binaries-not-in-git.txt`.
- Unchanged: frozen prereg/grid/amendment/v5/v6/proof bytes, analysis manifest 882dd4a4, memsub 2eee4228.

## Unresolved
- Final billing: re-fetch at 19:15Z into `attempt-2/97-billing-hourly-final-20261007.json`.
- Cause/effect of the missing L20 grad_norm in learned-n32-s1: undetermined.
- Next experiment: none authorized. Codex 21728 recommends inspecting the retained gradient / empty-read /
  write-read alignment evidence before choosing ONE targeted follow-up.
