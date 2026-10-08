# M4-SGM P2 pilot run — learned, N=32, seed=0

Label: **frozen-qwen3-0.6b-base+taskhead** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.012 (12/1024) | 0.006 | 13.7 | 0.9999999664723873 |
| heldout_bank_derange | 0.012 (12/1024) | 0.006 | 13.7 | 0.9999999664723873 |
| heldout_coord_shuffle | 0.012 (12/1024) | 0.006 | 13.7 | 0.9999999664723873 |
| heldout_read_offset | 0.012 (12/1024) | 0.006 | 13.7 | 0.9998867872636765 |
| heldout_query_off | 0.012 (12/1024) | 0.006 | 13.7 | None |
| train_split_none | 0.004 (1/256) | 0.008 | 13.8 | 1.0 |

Chance = 0.0156. Wall seconds: 18795.
