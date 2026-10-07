# M4-SGM P2 pilot run — learned, N=32, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.072 (74/1024) | 0.015 | 10.4 | 0.5621013306081295 |
| heldout_bank_derange | 0.072 (74/1024) | 0.015 | 10.4 | 0.5620687602786347 |
| heldout_coord_shuffle | 0.049 (50/1024) | 0.012 | 10.4 | 0.5510749570094049 |
| heldout_read_offset | 0.021 (22/1024) | 0.009 | 10.4 | 0.921063784044236 |
| heldout_query_off | 0.022 (23/1024) | 0.009 | 10.4 | None |
| train_split_none | 0.074 (19/256) | 0.032 | 10.4 | 0.5623552496545017 |

Chance = 0.0156. Wall seconds: 21325.
