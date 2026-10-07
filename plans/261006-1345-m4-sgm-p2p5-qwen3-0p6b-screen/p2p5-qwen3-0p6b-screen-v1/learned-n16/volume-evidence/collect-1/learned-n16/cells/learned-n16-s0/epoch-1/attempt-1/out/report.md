# M4-SGM P2 pilot run — learned, N=16, seed=0

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.032 (33/1024) | 0.011 | 23.4 | 0.8410751069895923 |
| heldout_bank_derange | 0.032 (33/1024) | 0.011 | 23.4 | 0.8412355650216341 |
| heldout_coord_shuffle | 0.016 (16/1024) | 0.007 | 23.4 | 0.8324773379135877 |
| heldout_read_offset | 0.015 (15/1024) | 0.008 | 23.4 | 0.8901137656066567 |
| heldout_query_off | 0.015 (15/1024) | 0.008 | 23.4 | None |
| train_split_none | 0.027 (7/256) | 0.019 | 23.5 | 0.8429758111014962 |

Chance = 0.0156. Wall seconds: 16320.
