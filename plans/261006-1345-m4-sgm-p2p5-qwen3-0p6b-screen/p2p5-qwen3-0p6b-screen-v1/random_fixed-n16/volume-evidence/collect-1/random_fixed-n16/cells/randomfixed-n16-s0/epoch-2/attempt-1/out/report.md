# M4-SGM P2 pilot run — random_fixed, N=16, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.077 (79/1024) | 0.016 | 8.8 | 0.25416239865467105 |
| heldout_bank_derange | 0.079 (81/1024) | 0.016 | 8.8 | 0.25406029067562486 |
| heldout_coord_shuffle | 0.065 (67/1024) | 0.015 | 8.8 | 0.2548294396926849 |
| heldout_read_offset | 0.019 (19/1024) | 0.008 | 8.8 | 0.9730349306482822 |
| heldout_query_off | 0.019 (19/1024) | 0.008 | 8.8 | None |
| train_split_none | 0.066 (17/256) | 0.027 | 8.8 | 0.25344736999704764 |

Chance = 0.0156. Wall seconds: 2007.
