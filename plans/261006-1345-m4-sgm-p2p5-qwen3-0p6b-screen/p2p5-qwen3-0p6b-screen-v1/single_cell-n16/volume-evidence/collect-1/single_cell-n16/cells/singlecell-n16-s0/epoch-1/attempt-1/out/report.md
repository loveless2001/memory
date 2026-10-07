# M4-SGM P2 pilot run — single_cell, N=16, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.034 (35/1024) | 0.011 | 1.0 | 0.0 |
| heldout_bank_derange | 0.026 (27/1024) | 0.009 | 1.0 | 0.0 |
| heldout_coord_shuffle | n/a | | | |
| heldout_read_offset | 0.034 (35/1024) | 0.011 | 1.0 | 0.0 |
| heldout_query_off | 0.021 (21/1024) | 0.009 | 1.0 | None |
| train_split_none | 0.027 (7/256) | 0.019 | 1.0 | 0.0 |

Chance = 0.0156. Wall seconds: 15085.
