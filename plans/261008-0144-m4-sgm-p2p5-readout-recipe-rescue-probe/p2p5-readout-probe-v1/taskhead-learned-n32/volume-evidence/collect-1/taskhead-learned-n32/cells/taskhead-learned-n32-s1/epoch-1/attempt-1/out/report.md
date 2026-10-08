# M4-SGM P2 pilot run — learned, N=32, seed=1

Label: **frozen-qwen3-0.6b-base+taskhead** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.016 (16/1024) | 0.007 | 10.3 | 0.9920882734004408 |
| heldout_bank_derange | 0.016 (16/1024) | 0.007 | 10.3 | 0.9920787182636559 |
| heldout_coord_shuffle | 0.016 (16/1024) | 0.007 | 10.3 | 0.9920882731676102 |
| heldout_read_offset | 0.016 (16/1024) | 0.007 | 10.3 | 0.9407500589732081 |
| heldout_query_off | 0.016 (16/1024) | 0.007 | 10.3 | None |
| train_split_none | 0.016 (4/256) | 0.015 | 10.4 | 0.991952845826745 |

Chance = 0.0156. Wall seconds: 19622.
