# M4-SGM P2 pilot run — learned, N=16, seed=0

Label: **tiny-random-lm+taskhead+DIAGNOSTIC-filler-off** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.949 (972/1024) | 0.014 | 26.0 | 0.05687569128447212 |
| heldout_bank_derange | 0.017 (17/1024) | 0.008 | 26.0 | 0.04625492427265954 |
| heldout_coord_shuffle | 0.142 (145/1024) | 0.022 | 26.0 | 0.030793315699225055 |
| heldout_read_offset | 0.008 (8/1024) | 0.005 | 26.0 | 0.756013973383233 |
| heldout_query_off | 0.010 (10/1024) | 0.006 | 26.0 | None |
| train_split_none | 0.965 (247/256) | 0.021 | 26.0 | 0.08614624142913385 |

Chance = 0.0156. Wall seconds: 2846.
