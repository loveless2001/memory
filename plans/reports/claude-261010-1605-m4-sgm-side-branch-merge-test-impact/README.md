# Side-branch merge test impact (user 22634 "Merge"; NOT merged)

Trial merge of `m4-sgm-occupied-fill-v1` (8bbb703) into mvp (eaa018e) in a disposable detached worktree: no conflicts,
191 files. The branch changes 6 memsub files, so the memsub tree sha becomes d86639b9 (the B1–B3 binding).
Test method: `git archive` copies of both trees, each test file in its own `systemd-run` scope (3500M, swap 0, KILL
900 s), hermetic env (Modal pointed at a dead URL with invalid tokens, HF offline, PKPROBE_FORBID_MODEL=1). The first
whole-suite runs were cgroup-OOM-killed at about 67% (2500M; journalctl 16:02/16:05 local).

Result (`merge-test-delta.json`): base 1192 pass / 72 fail / 5 skip; merge 1277 / 96 / 5. **24 pass → fail, 0 fail → pass**;
the 109 branch-only tests all pass. Base failures are the same on both sides: untracked evidence absent from archive
copies, plus one residual-readout file OOM-killed at 3500M on both.
The 24 failures are closed P2.5 campaign contracts that correctly refuse a changed memsub:
- `pk_campaign_readings_orchestration_fast` (8), `pk_campaign_readings_runner` (6),
  `pk_control_plane_reaper_and_manifest_label` (6): "dependency manifest: memsub source differs";
- `p2p5_readout_probe_validation_contract` (1): frozen registry sha derived from the memsub tree;
- `pk_posthoc_validation_amendment` (2): amended binding mismatch.
Logs: `base-*.log` / `cand-*.log`; runner script `run-per-file-capped-pytest-base-vs-merge.sh`.

## Unresolved questions
- User: full merge (24 closed-campaign tests red on mvp), or keep code separate and tag?
