# M4-SGM P2 pilot run — single_cell, N=32, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.050 (51/1024) | 0.013 | 1.0 | 0.0 |
| heldout_bank_derange | 0.046 (47/1024) | 0.012 | 1.0 | 0.0 |
| heldout_coord_shuffle | n/a | | | |
| heldout_read_offset | 0.050 (51/1024) | 0.013 | 1.0 | 0.0 |
| heldout_query_off | 0.029 (30/1024) | 0.011 | 1.0 | None |
| train_split_none | 0.047 (12/256) | 0.024 | 1.0 | 0.0 |

Chance = 0.0156. Wall seconds: 10260.
