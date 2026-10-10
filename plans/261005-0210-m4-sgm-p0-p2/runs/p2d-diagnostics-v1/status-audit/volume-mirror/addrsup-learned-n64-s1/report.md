# M4-SGM P2 pilot run — learned, N=64, seed=1

Label: **tiny-random-lm+taskhead+DIAGNOSTIC-aux-addr-lambda0.1** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.019 (19/1024) | 0.008 | 4.4 | 5.8294058075776604e-08 |
| heldout_bank_derange | 0.018 (18/1024) | 0.008 | 4.4 | 5.626461296267979e-08 |
| heldout_coord_shuffle | 0.015 (15/1024) | 0.007 | 4.4 | 5.624023307681671e-08 |
| heldout_read_offset | 0.011 (11/1024) | 0.006 | 4.4 | 1.0 |
| heldout_query_off | 0.011 (11/1024) | 0.006 | 4.4 | None |
| train_split_none | 0.020 (5/256) | 0.017 | 4.4 | 2.0836210445907e-07 |

Chance = 0.0156. Wall seconds: 6860.
