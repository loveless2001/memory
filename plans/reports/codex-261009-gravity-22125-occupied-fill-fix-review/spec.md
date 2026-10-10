# occupied_softmax_fill_v1 — query-read fallback + anchor (spec, CPU-checked, NOT run on Qwen)

User 22113 "Go" = CPU-only spec/implementation/gradient checks. No GPU, no Modal, no Qwen forward. GPU stop (22058) still in force; any run needs a separate proposal + codex review + user go.
Answers codex review 22105 (`plans/reports/codex-261009-gravity-22104-fallback-proposal-review/review.md`).

## Rule (per bank = batch × layer × head, at a QUERY read)
- a = read address (cells), stencil weights w_c (9, sum 1), presence p_c, q = unit query; occupied cells j = bank entries before the query (queries never write), centres c_j, states S_j.
- m = Σ_c w_c p_c — original-stencil present mass (telemetry). u = Σ_c w_c (1 − p_c) — missing mass, computed DIRECTLY (r3, codex 22121: FP32 1 − m was ±1e-7 on fully supported reads → nonzero/negative fill and an outward anchor). u = 0 exactly when fully supported, never < 0. `query_empty_read_weight` (same definition as u) still recorded BEFORE any fill.
- r = Σ_c w_c S_cᵀq + u · Σ_j π_j S_jᵀq, π = softmax_j(−‖a − c_j‖²/τ), computed as softmax((2a·c_j − ‖c_j‖²)/τ) (same values; FP32-stable for far reads).
- empty bank → r = 0, anchor 0, no NaN (tested).
- fully supported → bitwise the spec read; fill and anchor exactly 0 (tested: codex's reproducer + 200 random fractional addresses). Continuous in a (B-spline weights vanish at the stencil edge; tested across a cell boundary). u keeps its gradient.
- anchor (training loss only) = u.detach() · (√(1 + d_min²) − 1), d_min = min_j ‖a − c_j‖; loss += λ · mean over queries × layers × batch × heads. Pseudo-Huber: gradient ≤ 1 per cell, toward the nearest occupied cell. Ties: torch.min picks one cell (measure-zero).
- τ = 1.0 cell², λ = 0.1: single preregistered values, no tuning. λ choice: a read stranded ~10 cells away adds ~0.9 to a ~4.2 (ln 64) loss. Arbitrary, stated as such.

## Scope
- Applies ONLY to query reads (`evaluate_query` → `step(query=True)`), in training AND evaluation (the fill is part of the lookup); the anchor only in the training loss.
- Source-ingestion reads/writes untouched → banks bitwise identical to baseline (tested on the tiny backbone). Ingestion-time reads can still escape; they don't feed the taskhead directly but shape later features.
- `address_mode` must be "learned".

## What the gradients do (CPU tests, `tests/test_sgm_occupied_cell_read_fallback.py`)
- Hard nearest-cell (codex example): address grad None. Soft fill: finite nonzero (`test_codex_example_fill_gives_soft_address_gradient`).
- Fill only REWEIGHTS stored cells: ‖a‖² cancels, so a read moved 45 cells further away, orthogonally to the cells' spread, gets the same fill and zero fill gradient along that axis (`test_fill_softmax_only_reweights_but_anchor_pulls_back`). No return pull from the fill.
- Anchor alone (no task loss), far-empty read (present mass exactly 0): descent direction points at the nearest occupied cell, |g| ≤ 1 (`test_fill_softmax_only_reweights_but_anchor_pulls_back`). It pulls toward ANY occupied cell → restores overlap, not the correct binding.
- Anchor recipients: everything upstream of the read address — AddressMLP, that layer's q_proj (a_read = AddressMLP(q)), and earlier adapters/features through the frozen backbone. NOT AddressMLP-only (unlike A2's pair loss). u is detached inside the anchor only; d_min and a are not. Reduction: mean over queries × layers × batch × heads, then × λ. Checked through the full runtime (`test_anchor_alone_reaches_the_address_mlp`).
- Stored content: the fill keeps the bank's graph (no detach): grad into each stored state = π_j·q exactly (`test_fill_gradient_reaches_stored_content`).

## Identity / parity
- `SGMConfig.read_fallback` ("off" | "occupied_softmax_fill_v1"), `read_fallback_tau`, `read_fallback_anchor`; serialized only when on → every existing policy_id unchanged (tested against Stage A A0 + probe s0 manifests). Non-default τ/λ with "off" rejected.
- Default-off parity: tiny backbone, 4 updates + evals, CPU 1 thread: params/telemetry/policy sha identical pre-change (HEAD 95856b1) vs changed tree (`parity-before-HEAD-95856b1.json` = `parity-after-working-tree.json`).
- Result label: `+VARIANT-occupied_softmax_fill_v1-anchor0.1` (P2.5); `read-fallback` flag (tiny).

## Telemetry added (only when on)
Eval: `query_fully_absent_fraction` (m == 0 exactly: read carried entirely by the fill), `query_without_occupied_fraction`, `query_nearest_occupied_cells_mean`, `query_fill_support_cells_mean` (exp entropy of π). Train rows: `read_anchor` (unscaled). Original-stencil absence stays `query_empty_read_weight`. Not logged: read-feature variation.

## What a later run could / could not show (proposal shape only — NOT authorized)
- B1: exact A0 settings (probe s0 PilotConfig, lr 3e-3, 100 updates, filler-0 phase, heldout seed 4242 evals at 0/25/50/75/100) + this variant.
- Retention judged on ORIGINAL-stencil `query_empty_read_weight` at 100: ≤ 0.2 kept / ≥ 0.9 escaped (Stage A bands). Escaped + high fully-absent fraction = the fill carries the reads: label "mechanical, lookup changed", not restored routing.
- The 100-update gate targets routing/mechanics; it is not designed to show retrieval (not a claim that retrieval cannot emerge by 100). Retrieval needs a longer, separately approved run with held-out gain + bank_derange intervention. Fill + anchor = bundle; no attribution between them.
- Cost basis: A0 child 642 s × $0.00066544/s (listed L40S + 4 CPU + 32 GiB) ≈ $0.43 + startup/shutdown + unprofiled fill overhead. Local RTX 3060 Laptop (6 GB) = $0 but uses the GPU (user's call); fit unknown.

## Full SGM suite (CPU, `sgm-suite-cpu.txt`): 37 failed / 575 passed / 2 skipped
- New fallback tests: 13/13 pass (r2: + stored-content gradient, far-empty assert; r3: + exact fully-supported check) (`test_sgm_occupied_cell_read_fallback.py`).
- 12 failures ALSO fail on unchanged HEAD 95856b1 (`sgm-suite-failed-ids-rerun-at-HEAD.txt`, memsub sha 2eee4228 restored for that rerun, files sha-verified after). Cause: cleanup group A (user 22029, receipt c3651b1) deleted `…/learned-n32-s1/epoch-1/gen-30-step1500.pt`, the terminal checkpoint the P2.5 post-hoc amendment (a17cd40) binds. Not on codex's protected list; I missed it at cleanup time. Pre-existing, not caused by this change.
- 25 failures only after the change (`failed-only-after-change.txt`): closed P2.5 PK campaign readings/reaper/amendment/registry tooling binds memsub source sha 2eee4228 and refuses ("dependency manifest: memsub source differs") once memsub changes. Guards working as designed. Hence this variant lives on branch `m4-sgm-occupied-fill-v1`; mvp keeps memsub = 2eee4228 (also the Stage A geometry index binding).

## Unresolved
- Where the variant should live long-term: side branch (now) vs mvp with closed-campaign source-binding tests re-scoped (codex-owned tooling; not changed here).
- Recover the deleted s1 terminal checkpoint (Modal volume read, if it still exists) or record the 12 tests as evidence-unavailable.
- Fill overhead on GPU (per query read: gathers every occupied cell; ingestion unchanged).
- Whether λ = 0.1 is too weak/strong vs the escape push (no tuning planned).
- Whether to also anchor ingestion reads (not done: YAGNI, changes recurrence).
