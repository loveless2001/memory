# B2 manually stopped: shutdown verified; checkpoint 750 retained; no final readout

User #gravity 22196 requested stopping B2 and resuming later. The owner stopped the local client at 07:54:07Z. Independent live verification confirms the bound app `ap-VsAmnu1E7eS5rXLrKD7vXd` **stopped at 07:54:15Z, tasks 0, containers 0**. The launcher exited 1 at 07:54:17Z; cleanup exited 0 at 07:54:22Z and independently reported `stopped_verified` in 5.0 seconds. Its stop command's return code 1 means the app was already stopped. The fixed `SIGTERM (outer timeout)` label in the handler does not establish that the deadline fired: this was the requested manual stop, four hours before the original deadline.

## Protected resume evidence

The exact Volume run directory was retrieved read-only after shutdown. No GPU collector, training, evaluation forward pass, restore, remote write, retry, or new launch was performed. The CLI initially failed when a nonexistent local directory was treated as a file; the failed log is retained. Downloading into a new, pre-created directory succeeded without overwriting anything.

- **Checkpoint after exactly 750 optimizer updates:** [resume.pt](volume-evidence-verified/b2-run-v1/B2/resume.pt), 25,018,453 bytes, SHA256 `cd1a7e72cbbf4fc2cf92e029395c7e4f78a727d2b6d165b5030bacc1bd753394`.
- Exact original PilotConfig, base manifest, script, memsub `d86639b9…`, and campaign identity verified against the immutable 24b1432 snapshot. Original Volume campaign marker and start Dict deadline remain `1791546912.6074162` (11:55:12Z).
- One admitted start, task `ta-01M4FJAEGRVPR8T179Y5848N2R`, claimed at 05:31:38Z; start-2 and start-3 remain unused.
- Saved state contains 46 finite FP32 parameter tensors, AdamW group/44 state entries, data-generator RNG, CPU RNG, and one CUDA RNG state. All stored tensor values are finite. This verifies stored-state integrity; it does not certify a CUDA restore or gradient coverage of every parameter.
- Checkpoint telemetry has 83 rows and is an exact prefix of the 86-row full partial telemetry. The final logged training step is 770, recorded after its optimizer update, proving **at least 771 updates completed**. Continuing from 750 replays at least 21 completed updates; the exact unlogged tail is unknown. Preserve those post-checkpoint rows as partial/replayed evidence.

All retrieved files, per-start stdout/stderr, identities, Dict state, stop receipts, and raw billing/lifecycle results are retained here. `verify-saved-state.py` provides the offline checks; `saved-state-verification.json` records their results. The verified checkpoint is stored locally as well as on the Volume and must be bound by this exact hash in a future resume amendment. It is a real optimizer/RNG training checkpoint, not merely final inference weights.

## Scientific status: INTERRUPTED_PARTIAL

| Dev update | Correct / 256 | Pre-fill absent weight |
| --- | ---: | ---: |
| 0 | 9 | 0.046701 |
| 100 | 8 | 0.260050 |
| 200 | 4 | 0.368328 |
| 300 | 3 | 0.160721 |
| 400 | 3 | 0.179665 |
| 500 | 3 | 0.112262 |
| 600 | 1 | 0.155652 |
| 700 | 3 | 0.159188 |

Every collected dev row passes the registered evaluator schema. At update 700, the original read's absent mass is inside the <=0.2 band. Fully absent reads are 5.3955%; no reads lack an occupied bank; mean nearest-cell distance is 0.5627 and fill support is 5.7779 cells. These describe routing support. Dev correct fell from 9 to 3, so no held-out gain is observed in this partial segment. Neither occupancy nor restored support demonstrates useful retrieval.

The final 1500-update evaluation, bank-derangement intervention, final result/manifest, and final parameter artifact do not exist. The registered final classifier returns INVALID on this incomplete trajectory. **Do not issue a final memory-use pass/fail or recipe-failure verdict.** The stopped partials remain separately interpretable.

Training loss includes 0.1 times the anchor. `loss-decomposition.json` preserves the subtraction: latest task CE is 4.13613, compared with uniform CE ln(64)=4.15888. The last ten logged task CEs range from 4.13613 to 4.19357. These noisy individual batches do not establish task learning or harm. Median logged training-step time is 10.6853 seconds; the longer-input phase starting at update 1000 was not reached or profiled.

## Billing and future budget

The first app-only snapshot at 07:56Z reports **$5.69262133 provisional**, across hours 05/06/07: $1.13241043 / $2.39521120 / $2.16499970. Resources: L40S $4.63452388, CPU $0.44966765, memory $0.60842980. The 07:00 hour was open when that report was captured. **One recheck after 08:05Z**, with all queried hours closed, returns the same total: delta **$0.00000000**. Both raw reports and their Decimal reconciliations are preserved. Volume retention and download transfer are separate from these app rows; the total is before credits and allowances. Collection/backfill may still change it. [Modal billing documentation](https://modal.com/docs/guide/billing)

The entire app lifetime was 8,947 seconds, including queue time. At the original conditional rate $0.00067854/second, reserving that whole lifetime would account for **$6.07089738** for this first segment. This is a conservative ledger input under the original CPU/stop assumptions, not a settled invoice or external billing guarantee. The arithmetical $17 minus the provisional bill is not automatically a cleared resume reserve. A future package must account for the first segment plus backfill/transfer/storage and the new execution/shutdown envelope under the **same total $17**, including any replayed work.

## Resume preparation boundary

The original job was locally detached by setsid/nohup but **Modal-ephemeral without --detach**, so it depended on the PC/client connection. I should have highlighted this before clearance. Modal documents that ordinary ephemeral Apps stop when the client exits/disconnects, and that `--detach` changes this; deployed Apps can persist independently. [Modal app lifecycle documentation](https://modal.com/docs/guide/apps)

User's stop/resume-later request supports free CPU preparation. A fresh deadline and a host-independent dispatch method require an explicit amendment and independent review before the next paid dispatch. Preserve the original deadline, start-1 record, stop evidence, and this checkpoint rather than rewriting the interrupted segment. Maintain the three-start total and use the exact same recipe, state, RNG, and held-out schedule. The new execution must enforce its remaining-budget deadline and shutdown without relying on this PC remaining online, retain durable dispatch IDs and failure/partial records, and preserve both app IDs for combined billing if a new app is used.

No resume, deadline extension, budget reset, second seed, additional arm, or integration is launched or cleared by this terminal audit. The owner has these requirements in #gravity 22200/22201. The original B2 app is stopped; there is a concrete, protected stop point.
