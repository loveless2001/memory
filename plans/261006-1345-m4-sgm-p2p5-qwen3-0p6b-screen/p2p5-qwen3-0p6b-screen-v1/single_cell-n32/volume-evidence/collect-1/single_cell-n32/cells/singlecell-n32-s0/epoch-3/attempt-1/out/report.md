# M4-SGM P2 pilot run — single_cell, N=32, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.075 (77/1024) | 0.016 | 1.0 | 0.0 |
| heldout_bank_derange | 0.071 (73/1024) | 0.015 | 1.0 | 0.0 |
| heldout_coord_shuffle | n/a | | | |
| heldout_read_offset | 0.075 (77/1024) | 0.016 | 1.0 | 0.0 |
| heldout_query_off | 0.018 (18/1024) | 0.008 | 1.0 | None |
| train_split_none | 0.055 (14/256) | 0.028 | 1.0 | 0.0 |

Chance = 0.0156. Wall seconds: 10489.
