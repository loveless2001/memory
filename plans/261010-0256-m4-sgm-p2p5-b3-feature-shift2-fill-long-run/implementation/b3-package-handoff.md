# B3 package handoff (for codex package audit; NOT a launch)

Branch `m4-sgm-occupied-fill-v1` (worktree `memory-occupied-fill-v1-worktree`). Proposal **v0.3** `c6a3ae4`
(`proposal-v0.3.md` sha 531544df4512d4f8…, building on v0.2 fdc37202…). Status: CPU prep cleared (codex 22475/22479),
crash repair PASS (22511), Volume measurement accepted as CPU proxy (22512). **Paid package clearance and the user's
$17 cap are pending. No model, cloud or paid action has been taken.**

## 1. What B3 is
B2 recipe exactly + `sgm.feature_shift = 2` (a BUNDLE: wider q/k/v/beta inputs, so different init, and the query's
2nd block = last source VALUE for updates 0–999 / last FILLER from 1000 and in all dev evals). Seed 4242 = reused,
inspected DEV data. Gate unchanged: memory_used iff final ≥ 12/256 AND bank-derange drop ≥ 6; paired against B2's
5/256 = 5/256. Positive wording only: "met the exploratory memory-use screen on heldout dev episodes, this seed
(shift2 bundle)". The offline V+K probe (3d7b4d1) does not certify a live shift2 representation.

## 2. Files and hashes (sha256 prefix)
| file | commit | sha256 |
|---|---|---|
| `modal-runners/modal-m4-sgm-p2p5-b3-shift2-fill-long-run-runner.py` | bb3d7fc | f11427f8f000d29d |
| `scripts/sgm-p2p5-b3-shift2-fill-long-run-train.py` | bb3d7fc | 3f653b79fa70b5b2 |
| `tests/test_sgm_p2p5_b3_shift2_fill_long_run.py` | bb3d7fc | 83ce05bc7f1b225c |
| `implementation/b3-mutation-checks.py` (v3) | b01ec10 | 4ba4e7bb6ae0e4a2 |
| `implementation/b3-mutation-checks-v3.json` | b01ec10 | c3fd43c7401d230e |
| `implementation/b3-mutation-checks-v2.json` (bound by 22511) | 2186950 | 6270f67b8d9c6f73 |
| `implementation/b3-mutation-checks.json` (v1, SUPERSEDED: pre-crash classification) | bb3d7fc | 78237b934ed502a2 |
| `implementation/b3-retained-volume-size-measurement.py` | 479cabd | ce7f488d4342f264 |
| `implementation/b3-retained-volume-size-measurement.json` | 479cabd | 37a9c15dffe72998 |

Unchanged/bound: memsub tree `d86639b9…` (= B2; `EXPECT_MEMSUB_SHA256`), base image `im-A7BXMB8v1cVYRvC9pMqZ3i`,
pinned torch 2.7.1+cu126 / transformers 4.55.2, input manifest `…/probe-taskhead-learned-n32-s0-run_manifest.json`.

## 3. Evidence
- `pytest tests/test_sgm_p2p5_b3_shift2_fill_long_run.py`: **32 passed** (systemd scope, MemoryMax 2000M, swap 0).
  Includes: config = B2 + shift2 only; adapter widths 2048 and 3,744,604 params without Qwen; tiny-backbone CPU run
  finite + crash-after-checkpoint resume bit-identical; terminal marker on every non-interruption outcome; refusals;
  platform-interruption resume; fresh/write-once deadline; ledger = v0.3; `--yes` cleanup on a deployed-app CLI fake;
  bounded re-check loop; cloud sentinels.
- Mutants v3 (disposable `git archive HEAD` copy; per-pytest scope 2000M/swap 0/KILL 300 s; parent in a 512M scope;
  child output to file, bounded tail): baseline 32 passed; **11/11 CAUGHT by the exact expected test id**, rc 1.

## 4. Procedure (only after codex package PASS + user cap; chat_read right before each paid step)
Python = `/home/lenovo/projects/memory/.venv/bin/python`, cwd = worktree root, HEAD clean at the cleared commit.
1. `python <runner> precheck` — read-only: Dict/Volume fresh, memsub bound. Stop on anything but `ok`.
2. `python -m modal deploy <runner>`.
3. `python <runner> spawn <new local out>` — re-checks, records app id, writes the write-once deadline
   (spawn + 23,400 s), spawns ONE call. Capture full output to a file; check `modal container list` before ANY re-run.
4. `setsid nohup python <runner> watch <out> > <out>/watch.log 2>&1 < /dev/null &` — on call return or deadline +
   grace → `cleanup-verify`. Register a chat_wait on it.
5. `python <runner> collect <out>` → gate readout (no resume.pt fetched); `status` is read-only anytime.
6. `python <runner> cleanup-verify <out>` if watch did not reach `stopped_verified`.
- **Host-independent:** training (deploy + spawn; child timeout at deadline − 120 s may return normally; worker
  SIGKILL at the deadline cannot). **PC-dependent:** watch / cleanup-verify. Call completion ≠ zero containers or
  zero charges; deployed + zero containers ≠ stopped_verified.
- Starts: ≤ 3 TOTAL (initial + ≤ 2 resumptions), ONLY via Modal's own retry after a platform interruption.
  Prohibited: retry after a run-side failure, a manual re-spawn/new app/redeploy, extension, second seed.

## 5. Ledger (runner `ledger()`, asserted by test)
Rate = L40S $0.000542 + 1.25 × 4 × $0.0000131 + 32 × $0.00000222 = **$0.00067854/s**.
Compute reservation (23,400 + 300 s) = **$16.081398**; + $0.10 build allowance = **$16.181398**; cap ask **$17**,
headroom $0.818602. Conditional on: ≤ 5 billed CPU cores; ≤ 23,700 aggregate billed container-seconds across ALL
starts incl. startup/refusal/retry tails; memory ≤ 32 GiB; app stopped within the cleanup window; unchanged rates;
storage/transfer small and UNPRICED. Unenforced: CPU overuse beyond margin, billing tails, PC-down delaying cleanup.
B2's $10.92347 is a usage snapshot, not a settled bill. Throughput is UNPROFILED (accepted risk: a slow run ends at
the deadline with partial evals and no gate readout).

## 6. Retained Volume (supersedes proposal v0.3's "≤ ~155 MB")
Measured CPU payload proxy (`479cabd`): `resume.pt` = 45,256,523 B (1.007 × params + 2 Adam moments);
`checkpoint_steps = []`. Normal path: final ≈ 61.5 MB, save peak ≈ 106.7 MB. **Pathological path** (a crash during
the FIRST save on both permitted resumptions archives two `.tmp` files): final 151,869,268 B, **save peak
197,125,791 B** (codex 22512 arithmetic) → **use ~200 MB as the allowance (an estimate)**. Not an exact GPU bound:
CUDA RNG state omitted (CPU run), identity is a placeholder, telemetry is a B2 proxy, other metadata/headers excluded.
Storage/transfer remain an unpriced cap assumption.

## 7. Risks / unverified
- Whether Modal retries a SPAWNED call after preemption is unverified (B2 never exercised it): a preemption may end
  the campaign; any manual re-spawn needs a NEW approval.
- Unprofiled shift2 throughput/memory (see §5). Shift2 is a bundle: a positive result is not attributable to key
  information alone. Seed 4242 is reused dev data; one seed.
- Cleanup is PC-dependent; if the PC is down the deployed app idles (zero containers) until cleanup-verify runs.
- 2026-10-10 local OOM (my v1 mutation harness) — repaired and audited (22511); no remote effect.

## Unresolved questions
1. Codex: package PASS / REVISE?
2. User (after PASS): approve the $17 cap for one B3 campaign under §4–§6?
