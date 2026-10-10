# M4-SGM P2 pilot run — learned, N=32, seed=1

Label: **tiny-random-lm+taskhead+DIAGNOSTIC-aux-addr-lambda0.1** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.117 (120/1024) | 0.020 | 7.0 | 8.013629940850989e-05 |
| heldout_bank_derange | 0.013 (13/1024) | 0.007 | 7.0 | 3.335714293946357e-05 |
| heldout_coord_shuffle | 0.056 (57/1024) | 0.014 | 7.0 | 8.25077764321537e-05 |
| heldout_read_offset | 0.016 (16/1024) | 0.007 | 7.0 | 0.9938154686242342 |
| heldout_query_off | 0.016 (16/1024) | 0.007 | 7.0 | None |
| train_split_none | 0.117 (30/256) | 0.041 | 7.0 | 1.7670235170630377e-06 |

Chance = 0.0156. Wall seconds: 5959.
