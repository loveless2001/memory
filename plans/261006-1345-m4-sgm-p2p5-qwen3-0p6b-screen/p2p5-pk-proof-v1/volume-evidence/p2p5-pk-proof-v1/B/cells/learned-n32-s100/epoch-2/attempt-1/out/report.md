# M4-SGM P2 pilot run — learned, N=32, seed=100

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.000 (0/64) | 0.000 | 16.6 | 0.1961287674198502 |
| heldout_bank_derange | 0.000 (0/64) | 0.000 | 16.6 | 0.196149688280002 |
| heldout_coord_shuffle | 0.031 (2/64) | 0.042 | 16.6 | 0.19611876877343093 |
| heldout_read_offset | 0.031 (2/64) | 0.042 | 16.6 | 0.7975219637155533 |
| heldout_query_off | 0.031 (2/64) | 0.042 | 16.6 | None |
| train_split_none | 0.000 (0/128) | 0.000 | 16.9 | 0.19611381505465175 |

Chance = 0.0156. Wall seconds: 261.
