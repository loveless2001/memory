# M4-SGM P2 pilot run — learned, N=32, seed=99

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.016 (1/64) | 0.031 | 16.2 | 0.43740560859441757 |
| heldout_bank_derange | 0.016 (1/64) | 0.031 | 16.2 | 0.4374803230166435 |
| heldout_coord_shuffle | 0.000 (0/64) | 0.000 | 16.2 | 0.4373630881309509 |
| heldout_read_offset | 0.000 (0/64) | 0.000 | 16.2 | 0.742483377456665 |
| heldout_query_off | 0.000 (0/64) | 0.000 | 16.2 | None |
| train_split_none | 0.023 (3/128) | 0.026 | 16.4 | 0.4363615810871124 |

Chance = 0.0156. Wall seconds: 225.
