# M4-SGM P2 pilot run — learned, N=64, seed=0

Label: **tiny-random-lm+taskhead+DIAGNOSTIC-filler-off** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.025 (26/1024) | 0.009 | 99.0 | 0.04075426336651872 |
| heldout_bank_derange | 0.010 (10/1024) | 0.006 | 99.0 | 0.040263418581375277 |
| heldout_coord_shuffle | 0.019 (19/1024) | 0.008 | 99.0 | 0.04071298074716906 |
| heldout_read_offset | 0.024 (25/1024) | 0.010 | 99.0 | 0.28964714211178944 |
| heldout_query_off | 0.011 (11/1024) | 0.006 | 99.0 | None |
| train_split_none | 0.020 (5/256) | 0.017 | 99.5 | 0.05399013403473418 |

Chance = 0.0156. Wall seconds: 6196.
