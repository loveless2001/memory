# M4-SGM P2 pilot run — random_fixed, N=32, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.130 (133/1024) | 0.021 | 8.6 | 0.1955293942392018 |
| heldout_bank_derange | 0.133 (136/1024) | 0.020 | 8.6 | 0.19544052752462449 |
| heldout_coord_shuffle | 0.079 (81/1024) | 0.017 | 8.6 | 0.18802559775394911 |
| heldout_read_offset | 0.021 (21/1024) | 0.008 | 8.6 | 0.8786793604958802 |
| heldout_query_off | 0.020 (20/1024) | 0.008 | 8.6 | None |
| train_split_none | 0.098 (25/256) | 0.032 | 8.6 | 0.19478292064741254 |

Chance = 0.0156. Wall seconds: 12259.
