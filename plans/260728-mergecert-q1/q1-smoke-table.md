| arm (matched budget) | agg KL | agg accDelta | pointwise lost|prior | merge - eviction 95% CIs |
|---|---:|---:|---:|---|
| eviction 0.25 (existing row) | 0.0413 | +0.000 | 1.000 | - |
| eviction 0.40 (existing row) | 0.0391 | +0.000 | 1.000 | - |
| frozen subsample (reference) | 0.2566 | +0.063 | 0.188 | - |
| unfrozen compactor (reference) | 0.1385 | +0.042 | 0.083 | - |
| MERGE 0.25 | 0.0350 | +0.000 | 0.500 | KL -0.0064 [-0.0165, +0.0038]; accDelta +0.0000 [+0.0000, +0.0000]; lost|prior -0.5000 [-1.0000, +0.0000] |
| MERGE 0.40 | 0.0465 | -0.333 | 0.500 | KL +0.0074 [+0.0019, +0.0128]; accDelta -0.3333 [-0.6667, +0.0000]; lost|prior -0.5000 [-1.0000, +0.0000] |
| zero-compression control | 0.0000 | +0.000 | 0.000 | - |
