# M4-SGM P2 pilot run — learned, N=32, seed=0

Label: **tiny-random-lm+taskhead+DIAGNOSTIC-aux-addr-lambda0.1** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.029 (30/1024) | 0.010 | 4.2 | 1.2015083400682823e-06 |
| heldout_bank_derange | 0.020 (20/1024) | 0.008 | 4.2 | 4.441786833763143e-07 |
| heldout_coord_shuffle | 0.021 (22/1024) | 0.009 | 4.2 | 1.181193218951885e-06 |
| heldout_read_offset | 0.017 (17/1024) | 0.008 | 4.2 | 1.0 |
| heldout_query_off | 0.017 (17/1024) | 0.008 | 4.2 | None |
| train_split_none | 0.008 (2/256) | 0.011 | 4.2 | 2.3411953739788192e-07 |

Chance = 0.0156. Wall seconds: 6072.
