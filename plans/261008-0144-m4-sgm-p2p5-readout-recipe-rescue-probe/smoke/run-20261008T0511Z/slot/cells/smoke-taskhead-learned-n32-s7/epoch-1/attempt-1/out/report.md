# M4-SGM P2 pilot run — learned, N=32, seed=7

Label: **frozen-qwen3-0.6b-base+taskhead** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.000 (0/16) | 0.000 | 14.3 | 0.989596139639616 |
| heldout_bank_derange | 0.000 (0/16) | 0.000 | 14.3 | 0.9895995296537876 |
| heldout_coord_shuffle | 0.000 (0/16) | 0.000 | 14.3 | 0.9895961359143257 |
| heldout_read_offset | 0.000 (0/16) | 0.000 | 14.3 | 0.9784858673810959 |
| heldout_query_off | 0.000 (0/16) | 0.000 | 14.3 | None |
| train_split_none | 0.000 (0/32) | 0.000 | 14.3 | 0.9877056702971458 |

Chance = 0.0156. Wall seconds: 612.
