| arm (matched budget) | agg KL | agg accDelta | pointwise lost|prior | merge - eviction 95% CIs |
|---|---:|---:|---:|---|
| eviction 0.25 (existing row) | 0.0303 | -0.029 | 0.550 | - |
| eviction 0.40 (existing row) | 0.0335 | -0.071 | 0.650 | - |
| frozen subsample (reference) | 0.2566 | +0.063 | 0.188 | - |
| unfrozen compactor (reference) | 0.1385 | +0.042 | 0.083 | - |
| MERGE 0.25 | 0.0360 | -0.075 | 0.400 | KL +0.0057 [-0.0057, +0.0173]; accDelta -0.0458 [-0.0958, +0.0000]; lost|prior -0.1500 [-0.3500, +0.0500] |
| MERGE 0.40 | 0.0591 | -0.133 | 0.425 | KL +0.0256 [+0.0079, +0.0496]; accDelta -0.0625 [-0.1750, +0.0458]; lost|prior -0.2250 [-0.4000, -0.0500] |
| zero-compression control | 0.0000 | +0.000 | 0.000 | - |
