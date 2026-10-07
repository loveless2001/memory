# M4-SGM P2 pilot run — memory_off, N=32, seed=1

Label: **frozen-qwen3-0.6b-base+residual-head** — mechanism evidence on a frozen RANDOM tiny backbone; not a pretrained/frozen-Qwen result.

| eval | accuracy | 95% half-width (episode) | eff. cells | query empty-read wt |
|---|---|---|---|---|
| heldout_none | 0.016 (16/1024) | 0.007 | 0.0 | None |
| train_split_none | 0.012 (3/256) | 0.013 | 0.0 | None |

Chance = 0.0156. Wall seconds: 4918.
