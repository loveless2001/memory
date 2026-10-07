# M4-SGM P2 pilot run — learned, N=32, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.063 (65/1024) | 0.015 | 10.4 | 0.7837156986352056 |
| heldout_bank_derange | 0.062 (64/1024) | 0.014 | 10.4 | 0.783441721694544 |
| heldout_coord_shuffle | 0.056 (57/1024) | 0.014 | 10.4 | 0.7818131560925394 |
| heldout_read_offset | 0.037 (38/1024) | 0.011 | 10.4 | 0.9114958820864558 |
| heldout_query_off | 0.037 (38/1024) | 0.011 | 10.4 | None |
| train_split_none | 0.055 (14/256) | 0.026 | 10.3 | 0.7829732829704881 |

Chance = 0.0156. Wall seconds: 19265.
