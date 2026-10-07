# M4-SGM P2 pilot run — learned, N=16, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.022 (23/1024) | 0.009 | 12.1 | 0.8153835149714723 |
| heldout_bank_derange | 0.019 (19/1024) | 0.008 | 12.1 | 0.8153938591713086 |
| heldout_coord_shuffle | 0.016 (16/1024) | 0.008 | 12.1 | 0.8153835335979238 |
| heldout_read_offset | 0.020 (20/1024) | 0.009 | 12.1 | 0.9097944339737296 |
| heldout_query_off | 0.022 (23/1024) | 0.009 | 12.1 | None |
| train_split_none | 0.031 (8/256) | 0.020 | 12.1 | 0.8152133938856423 |

Chance = 0.0156. Wall seconds: 16136.
