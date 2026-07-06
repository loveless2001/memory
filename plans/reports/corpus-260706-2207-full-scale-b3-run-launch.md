# Full-Scale B.3 Run — Launch Record

Date: 2026-07-06 22:17 ICT · Modal app: `ap-UOU50VIYOOSiIZiGvA6urD` (detached)

## What is running

- **Corpus (done)**: 40,000 docs / ~927M est. tokens in `memsub-artifacts`
  volume (`corpus/*.jsonl`, deterministic append-only growth from the 7,232-doc
  test corpus, so prior doc_ids remain valid).
  financial 238M · legal 119M · code 154M · literature 416M tokens.
- **Generation (in flight)**: 32 spawned workers (`generate_domain_slice`),
  4 domains × 8 slices × 3,125 items = **100,000 item target** (spec range
  100–150k). H100, ~7 concurrent under quota; est. ~195 GPU-hours total,
  ~$770, ~1 day wall at current concurrency.
- **Resume safety**: each worker persists `{next_group, items}` to
  `corpus-mcq-full/<domain>/slice-NN.state.json` after every 100-doc group
  and commits the volume; restarts resume from the cursor. Re-spawning a
  finished slice is a no-op.

## How to check / finish (any session)

```bash
# progress: count of slice state files + sizes
uv run modal volume ls memsub-artifacts /corpus-mcq-full/financial

# when all workers are done (app tasks drain to 0):
uv run modal app list                      # ap-UOU50VIYOOSiIZiGvA6urD
uv run modal run modal-runners/modal-b3-corpus-pipeline.py::full_run_finalize
# -> merges to corpus-mcq-full/all-items.json + counts.json, then certifies
```

If workers died early (state files stuck), re-run:
`modal run --detach ::full_run_launch --target-items 100000 --slices-per-domain 8`
(idempotent: finished slices return immediately).

## Unresolved questions
- Modal GPU concurrency quota shapes wall time (7 concurrent observed at
  launch); nothing to fix, just latency.
