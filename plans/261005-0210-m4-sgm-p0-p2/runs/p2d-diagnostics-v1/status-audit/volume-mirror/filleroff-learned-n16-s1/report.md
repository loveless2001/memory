# M4-SGM P2 pilot run — learned, N=16, seed=1

Label: **tiny-random-lm+taskhead+DIAGNOSTIC-filler-off** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.954 (977/1024) | 0.013 | 22.7 | 0.007746719710482353 |
| heldout_bank_derange | 0.013 (13/1024) | 0.007 | 22.7 | 0.011570607630922325 |
| heldout_coord_shuffle | 0.158 (162/1024) | 0.023 | 22.7 | 0.007720279476345127 |
| heldout_read_offset | 0.016 (16/1024) | 0.007 | 22.7 | 0.7615326649975032 |
| heldout_query_off | 0.016 (16/1024) | 0.007 | 22.7 | None |
| train_split_none | 0.961 (246/256) | 0.022 | 22.4 | 0.00922185821614363 |

Chance = 0.0156. Wall seconds: 2982.
