# M4-SGM P2 pilot run — oracle, N=32, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head+DIAGNOSTIC-oracle-address** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 1.000 (1024/1024) | 0.000 | 117.0 | 0.0 |
| heldout_bank_derange | 0.013 (13/1024) | 0.007 | 117.0 | 0.8095703125 |
| heldout_coord_shuffle | 0.021 (21/1024) | 0.009 | 117.0 | 0.0 |
| heldout_read_offset | 0.014 (14/1024) | 0.007 | 117.0 | 0.8759765625 |
| heldout_query_off | 0.013 (13/1024) | 0.007 | 117.0 | None |
| train_split_none | 1.000 (256/256) | 0.000 | 117.0 | 0.0 |

Chance = 0.0156. Wall seconds: 21163.
