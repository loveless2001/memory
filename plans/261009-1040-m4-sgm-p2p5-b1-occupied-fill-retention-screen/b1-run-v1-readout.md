# B1 run v1 readout (one attempt, package v0.2 7e9213a)

Launch 2026-10-09 03:57:52Z (user 22134 go, $2.50 cap; codex 22137 clearance). App ap-ROPSmaSeABkUyr4X1d4RD2.

## Lifecycle
- Client exit 0 at 04:16:07Z; client wall 1087.9 s; queue gap 0.7 s; child rc 0, wall 1054 s (timeout 1500).
- Cleanup exit 0: `stopped_verified` in 5.3 s, 1 check — app stopped 11:16:07+07, tasks 0, container rows [].
- Manifest: memsub d86639b9… (bound), torch 2.7.1+cu126 / transformers 4.55.2, label `frozen-qwen3-0.6b-base+taskhead+VARIANT-occupied_softmax_fill_v1-anchor0.1`, policy m4-sgm:learned:sha256:23a1f6778b5596ea. trained_parameters.safetensors sha 96d40040… = manifest (file kept local, uncommitted, like A0).
- Billing PROVISIONAL: $0.70688 (03:00 + 04:00 UTC hourly buckets, captured 04:17:05Z while 04:00 not closed; backfill possible). Reservation $1.99, cap $2.50.

## Pre-registered readout (original-stencil absent mass, PRE-fill)
| dev step | 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|
| B1 absent | .047 | .442 | .456 | .382 | **.260** |
| A0 absent (same recipe, no variant) | .047 | .996 | .999 | 1.000 | .993 |
| B1 fully-absent fraction (fill carries all) | 0 | .218 | .148 | .145 | .132 |

- **band_at_100 = partial** (0.2 < .260 < 0.9); kept_through_100 = false. Pre-registered reading: reported as measured, no claim. Outcomes belong to fill+anchor together.
- Fill does not carry most reads: 13% fully absent at 100; mean nearest-occupied distance 0.80 cells.

## Beside (not criteria)
- Dev accuracy .035 → .012/.012/.012 → .031 (chance .016; A0 .035 → .016). No retrieval evidence (not designed to show).
- Train loss 4.23 → ~4.21 at 90 (ln 64 = 4.159); A0 settled ~4.16. B1 sits slightly ABOVE the uniform-prediction level.
- Read-address spread 0.97 → 10.6 cells (A0 plateau 3.8); occupancy 34 → 55 cells (A0 ~37): reads and writes both spread wider under B1.
- `read_anchor` 0.01 → 0.79 (update 10) → 0.44 (update 90).
- Step time 8.6–9.0 s vs A0 median 5.03 s (~75% overhead: the fill gathers every occupied cell per query read; occupancy grows). A 1500-step run at this rate ≈ 3.6 h optimizer time alone (≈ $8.7 at listed base rates, before evals/load/filler-40 phase).

## Unresolved
- Whether support keeps recovering past 100 (trend .456 → .260 over 50–100) or plateaus — not measured.
- Whether reads kept near cells ever become USEFUL (loss above ln 64 = reads currently add noise, not information) — needs a separately approved longer run.
- Cause of the wider spread (reads AND writes) — unmeasured.
