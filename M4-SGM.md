# M4-SGM — Sparse Growing Memory (research-only)

Status: **P0–P2 IN PROGRESS** (started 2026-10-05). Authorized in #gravity
msg 21068 ("commit the changes first then go, use modal for compute").
Design brief: [plans/261005-0210-m4-sgm-p0-p2/m4-sgm-design-spec-v0.1.md](plans/261005-0210-m4-sgm-p0-p2/m4-sgm-design-spec-v0.1.md).
Reviews: claude msg 21059 / [report](plans/reports/claude-261005-0155-m4-sgm-spec-review.md),
codex msgs 21060/21061/21063, convergence msgs 21064–21066.

This is a new experiment line. It does not reopen the reader/retrieval
campaign paused on 2026-09-11 (CONTEXT-POLICY.md). E1FULL stays NO-SHIP,
`max_certified_depth = 0`. Nothing here is wired into a deployment default.

## Starting point (P0)

- Commit: `53af8c3` on `mvp` (brief inspected `f67ff34`; the only differences
  are the three commits that recorded pre-existing worktree content: an
  artifact `.gitignore`, the paused campaign, the spec review). No
  interface the brief relies on changed.
- Environment: Python 3.12.13, torch 2.7.1+cpu, transformers 4.55.2,
  safetensors 0.5.3 (pinned; not upgraded).
- Baseline suite before M4: 562 passed, 53 failed, 2 skipped. The 53
  failures (`test_mergecert_q1_report.py`, 2 in
  `test_mergecert_campaign_contract.py`) reproduce on a clean `f67ff34`
  worktree: recorded MergeCert-Q1 provenance hashes no longer match the
  addendum edited by `f044ab2`. Pre-existing; historical provenance is not
  edited by M4.

## Agreed amendments to the brief (21064–21066)

1. P0–P2 reference = token-serial ingestion, full gradients, small nonzero
   output init (as briefed). Chunked ingestion, detached-source-feature
   training, a write gate and a Qwen3-0.6B pilot are registered follow-ups.
2. Phase-tagged tests (below); P2 is ephemeral/synthetic — SGM-10/11 are P4
   and real-archive sessions must not be accepted before them.
3. State is rebuilt after every optimizer step (fresh episodes per step).
4. Main memory controls re-ingest the source under each arm; query-time
   interventions are labelled diagnostics.
5. `ingest_source` is one transaction (fork + commit); rollback fixtures for
   overflow after an earlier layer wrote and late in a span.
6. Bounded load sweep vs the fixed single-bank control; routing failure is
   judged by causal address interventions + task results, not occupancy.
7. P3 registration will carry a descriptive, non-gating retrieval reference
   (existing shadow search is embedding/cosine; lexical is a separate arm).

## Registered deviation

`feature_shift=2` (projections see `[z_t, z_{t-1}]`, the delta-rule short-conv
idea) is used in the tiny P2 grid because a frozen RANDOM 4-layer backbone
does not reliably carry the key into the value token's hidden state. It is
part of the policy identity, the reference config keeps `feature_shift=1`,
and the grid includes a `noshift` ablation.

## Test map (phase of first requirement)

| ID | Phase | Status |
|---|---|---|
| SGM-01,02,03,04,05,06,07,08,09,15,16,17 | P1–P2 | implemented (`tests/test_sgm_*.py`) |
| SGM-19 | P2 | implemented (result labels) |
| SGM-18 | P3 | NOT IMPLEMENTED (no teacher/continuation scoring in P2) |
| SGM-10, SGM-11 | P4 | NOT IMPLEMENTED (no persistence / real archive in P2) |
| SGM-12, SGM-13, SGM-14, SGM-20 | P4 | NOT IMPLEMENTED (recovery / certification) |

## P2 synthetic load sweep — preregistration (frozen before launch)

Grid: `configs/m4_sgm_p2_grid.json` (49 runs, Modal CPU). Tiny frozen random
Qwen3 (4 layers, hidden 64), SGM at layers (1, 3), 2 heads, d_k = d_v = 8,
recent window 32 + 4 sinks, filler 40 → every binding is outside recent KV
at query time. N bindings ∈ {4, 8, 16, 32, 64}; 4 queries/episode; held-out
key and filler families; 600 steps × batch 16; seeds {0, 1}.

Arms: `learned`; `single_cell` (one cell, weight 1 — fixed single bank);
`random_fixed` (AddressMLP frozen, routing receives no gradient, init spread
4 cells); `oracle` (DIAGNOSTIC: address = key identity); `memory_off`
(re-ingested with SGM disabled). Ablations: `noshift` (learned/oracle at
N = 16, feature_shift = 1); `lmread` (frozen random LM-head readout, N = 16).

Readings (held-out, episode-level 95% intervals, both seeds):

- **R1 interface:** oracle accuracy well above chance (1/64) at every N. If
  oracle fails, the update/readout path is broken → stop and debug.
- **R2 capacity regime:** the smallest N where `single_cell` falls ≥ 20 pp
  below `oracle` is N*. No N* in range → the sweep cannot test routing.
- **R3 learned routing:** at some N ≥ N*, `learned` beats the stronger of
  `single_cell` / `random_fixed` by ≥ 5 pp in both seeds with intervals
  excluding zero, AND the read-offset diagnostic lowers `learned`
  accuracy. Otherwise "learned routing not demonstrated"; if `learned` ≈
  `single_cell` with few effective cells, the collapse hypothesis is
  supported for this design.
- **R4 memory use:** the shuffle diagnostic drops every memory arm toward chance.

These are mechanism readings on a random backbone. They do not establish
anything about frozen pretrained Qwen, recovery, or scaling.
