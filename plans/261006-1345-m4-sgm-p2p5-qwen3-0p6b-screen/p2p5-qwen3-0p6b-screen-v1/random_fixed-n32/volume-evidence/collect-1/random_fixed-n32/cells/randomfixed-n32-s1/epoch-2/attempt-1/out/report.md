# M4-SGM P2 pilot run — random_fixed, N=32, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.105 (108/1024) | 0.019 | 8.4 | 0.20009036550618475 |
| heldout_bank_derange | 0.102 (104/1024) | 0.019 | 8.4 | 0.20006796989036957 |
| heldout_coord_shuffle | 0.091 (93/1024) | 0.017 | 8.4 | 0.2027877035579877 |
| heldout_read_offset | 0.031 (32/1024) | 0.011 | 8.4 | 0.9909587057773024 |
| heldout_query_off | 0.031 (32/1024) | 0.011 | 8.4 | None |
| train_split_none | 0.121 (31/256) | 0.033 | 8.5 | 0.19955150937312283 |

Chance = 0.0156. Wall seconds: 12629.
