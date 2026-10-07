# M4-SGM P2 pilot run — oracle, N=32, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head+DIAGNOSTIC-oracle-address** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.981 (1005/1024) | 0.008 | 127.4 | 0.0 |
| heldout_bank_derange | 0.010 (10/1024) | 0.006 | 127.4 | 0.8447265625 |
| heldout_coord_shuffle | 0.015 (15/1024) | 0.007 | 127.4 | 0.0 |
| heldout_read_offset | 0.016 (16/1024) | 0.008 | 127.4 | 0.8671875 |
| heldout_query_off | 0.014 (14/1024) | 0.007 | 127.4 | None |
| train_split_none | 0.977 (250/256) | 0.018 | 127.4 | 0.0 |

Chance = 0.0156. Wall seconds: 20645.
