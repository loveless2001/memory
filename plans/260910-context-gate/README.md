# ContextGate v1 campaign

Design: [CONTEXT-GATE.md](../../CONTEXT-GATE.md).

**Completed:** [verified report](20260910-v1/REPORT.md). Nine controller
checkpoints trained; registered verdict `does_not_advance`. Hidden MLP test
accuracy 88.89%, surface MLP and always-retrieve 90.00%. Modal reported
$1.03092075 for the app; function elapsed time 875.3 seconds.

The campaign trains retrieval-utility controllers around a frozen
Qwen3-4B-Instruct-2507. It uses new controlled conversation data, not the
existing KV-compaction labels. Existing certification decisions are unchanged.

Initial submission: `20260910-v1`, Modal app
[`ap-eoBCSOVZ0Sdio1pNLJmIbO`](https://modal.com/apps/syntracts/main/ap-eoBCSOVZ0Sdio1pNLJmIbO).
The run directory's `launch.json` binds exact source hashes and function-call ID.
`artifacts/status.json` is the authoritative completion state after download.

Local validation:

- `tests/test_context_gate_experiment.py`: 11 passed.
- Python compilation and `git diff --check`: passed.
- Full fit/calibrate/evaluate path on synthetic arrays: passed, including
  three-seed checkpoint reloads and all ten reported arms.
- 1,800 rows / 600 conversations; no cross-split archive overlap.
- All three note views of each conversation stay in one split.

To retrieve artifacts after the run, from repository root:

```bash
context_gate_download="$(mktemp -d /tmp/context-gate-download.XXXXXX)"
.venv/bin/modal volume get memsub-artifacts /context-gate-v1/20260910-v1 "$context_gate_download"
mkdir -p plans/260910-context-gate/20260910-v1/artifacts
cp -a "$context_gate_download/20260910-v1/." plans/260910-context-gate/20260910-v1/artifacts/
.venv/bin/python plans/260910-context-gate/render_report.py plans/260910-context-gate/20260910-v1
```

The existing-directory destination is intentional: Modal CLI 1.5.1 otherwise
misclassifies a missing destination during recursive download. The failed
first download in this campaign wrote no files and did not restart compute.

The renderer checks artifact hashes and the local/remote source binding before
writing `REPORT.md`. A submitted app or a trained checkpoint alone does not
establish a positive experiment result.

Timing scope: batch capture records forward-pass time. Sequential replay also
includes tokenization, controller inference, and the executed answer branch.
BM25 indices and archive contents are already in memory for replay; disk/network
archive access and index construction are excluded. Output is a forced
single-token decision or answer, not long-form generation.
