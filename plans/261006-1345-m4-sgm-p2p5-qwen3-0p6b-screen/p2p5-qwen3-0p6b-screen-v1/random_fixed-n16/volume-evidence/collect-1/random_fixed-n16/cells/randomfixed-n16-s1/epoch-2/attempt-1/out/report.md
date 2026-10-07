# M4-SGM P2 pilot run — random_fixed, N=16, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.017 (17/1024) | 0.008 | 7.9 | 0.22126859594116155 |
| heldout_bank_derange | 0.017 (17/1024) | 0.008 | 7.9 | 0.22119669156042843 |
| heldout_coord_shuffle | 0.017 (17/1024) | 0.008 | 7.9 | 0.21898753055118192 |
| heldout_read_offset | 0.019 (19/1024) | 0.009 | 7.9 | 0.9353233959991485 |
| heldout_query_off | 0.019 (19/1024) | 0.008 | 7.9 | None |
| train_split_none | 0.016 (4/256) | 0.015 | 7.9 | 0.2197142948407418 |

Chance = 0.0156. Wall seconds: 2012.
