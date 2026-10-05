# p2-load-sweep-v2 — 49 runs

- registered steps (A1): 1500
- registered queries/episode: 4

| tag | arm | N | seed | steps | acc ± hw | derange | read+3 | eff cells | occ | β value | β filler |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lmread | learned | 16 | 0 | 1500 | 0.047 ± 0.013 | 0.009 | 0.023 | 24.4 | 43 | 0.754 | 0.564 |
| lmread | oracle | 16 | 0 | 1500 | 0.898 ± 0.019 | 0.013 | 0.011 | 57.8 | 153 | 0.784 | 0.691 |
| main | learned | 4 | 0 | 1500 | 0.882 ± 0.021 | 0.016 | 0.018 | 17.1 | 31 | 0.831 | 0.252 |
| main | learned | 4 | 1 | 1500 | 0.926 ± 0.016 | 0.020 | 0.016 | 16.1 | 30 | 0.848 | 0.368 |
| main | learned | 8 | 0 | 1500 | 0.877 ± 0.020 | 0.016 | 0.015 | 20.4 | 39 | 0.656 | 0.343 |
| main | learned | 8 | 1 | 1500 | 0.903 ± 0.017 | 0.012 | 0.014 | 25.4 | 48 | 0.715 | 0.395 |
| main | learned | 16 | 0 | 1500 | 0.052 ± 0.013 | 0.008 | 0.018 | 32.1 | 59 | 0.331 | 0.270 |
| main | learned | 16 | 1 | 1500 | 0.593 ± 0.031 | 0.016 | 0.016 | 24.6 | 46 | 0.434 | 0.313 |
| main | learned | 32 | 0 | 1500 | 0.021 ± 0.008 | 0.020 | 0.013 | 56.8 | 102 | 0.239 | 0.275 |
| main | learned | 32 | 1 | 1500 | 0.021 ± 0.009 | 0.014 | 0.016 | 72.5 | 125 | 0.292 | 0.309 |
| main | learned | 64 | 0 | 1500 | 0.020 ± 0.010 | 0.016 | 0.021 | 166.8 | 315 | 0.193 | 0.255 |
| main | learned | 64 | 1 | 1500 | 0.018 ± 0.008 | 0.021 | 0.020 | 160.4 | 287 | 0.206 | 0.259 |
| main | oracle | 4 | 0 | 1500 | 1.000 ± 0.000 | 0.017 | 0.016 | 21.2 | 45 | 0.993 | 0.877 |
| main | oracle | 4 | 1 | 1500 | 0.999 ± 0.002 | 0.016 | 0.018 | 21.2 | 45 | 0.975 | 0.869 |
| main | oracle | 8 | 0 | 1500 | 1.000 ± 0.000 | 0.018 | 0.017 | 36.5 | 81 | 0.988 | 0.885 |
| main | oracle | 8 | 1 | 1500 | 1.000 ± 0.000 | 0.013 | 0.013 | 35.9 | 81 | 0.940 | 0.851 |
| main | oracle | 16 | 0 | 1500 | 1.000 ± 0.000 | 0.015 | 0.013 | 68.2 | 153 | 0.958 | 0.879 |
| main | oracle | 16 | 1 | 1500 | 1.000 ± 0.000 | 0.013 | 0.014 | 69.4 | 153 | 0.979 | 0.873 |
| main | oracle | 32 | 0 | 1500 | 0.999 ± 0.002 | 0.016 | 0.016 | 136.1 | 297 | 0.977 | 0.869 |
| main | oracle | 32 | 1 | 1500 | 0.999 ± 0.002 | 0.012 | 0.011 | 136.3 | 297 | 0.971 | 0.870 |
| main | oracle | 64 | 0 | 1500 | 1.000 ± 0.000 | 0.016 | 0.010 | 266.7 | 585 | 0.973 | 0.863 |
| main | oracle | 64 | 1 | 1500 | 1.000 ± 0.000 | 0.015 | 0.017 | 266.4 | 585 | 0.972 | 0.865 |
| main | random_fixed | 4 | 0 | 1500 | 0.079 ± 0.016 | 0.014 | 0.020 | 85.0 | 167 | 0.849 | 0.736 |
| main | random_fixed | 4 | 1 | 1500 | 0.100 ± 0.018 | 0.012 | 0.060 | 69.0 | 129 | 0.852 | 0.731 |
| main | random_fixed | 8 | 0 | 1500 | 0.045 ± 0.013 | 0.019 | 0.027 | 80.5 | 155 | 0.672 | 0.624 |
| main | random_fixed | 8 | 1 | 1500 | 0.043 ± 0.012 | 0.021 | 0.029 | 67.5 | 126 | 0.713 | 0.618 |
| main | random_fixed | 16 | 0 | 1500 | 0.022 ± 0.009 | 0.011 | 0.017 | 86.3 | 170 | 0.343 | 0.391 |
| main | random_fixed | 16 | 1 | 1500 | 0.025 ± 0.009 | 0.018 | 0.022 | 77.2 | 149 | 0.333 | 0.381 |
| main | random_fixed | 32 | 0 | 1500 | 0.020 ± 0.008 | 0.022 | 0.021 | 101.5 | 209 | 0.180 | 0.243 |
| main | random_fixed | 32 | 1 | 1500 | 0.014 ± 0.007 | 0.015 | 0.018 | 90.2 | 179 | 0.197 | 0.276 |
| main | random_fixed | 64 | 0 | 1500 | 0.019 ± 0.008 | 0.021 | 0.018 | 114.4 | 240 | 0.107 | 0.184 |
| main | random_fixed | 64 | 1 | 1500 | 0.015 ± 0.007 | 0.020 | 0.018 | 102.1 | 214 | 0.112 | 0.182 |
| main | single_cell | 4 | 0 | 1500 | 0.557 ± 0.028 | 0.014 | 0.557 | 1.0 | 1 | 0.499 | 0.152 |
| main | single_cell | 4 | 1 | 1500 | 0.523 ± 0.027 | 0.012 | 0.523 | 1.0 | 1 | 0.534 | 0.140 |
| main | single_cell | 8 | 0 | 1500 | 0.111 ± 0.019 | 0.011 | 0.111 | 1.0 | 1 | 0.170 | 0.131 |
| main | single_cell | 8 | 1 | 1500 | 0.075 ± 0.015 | 0.015 | 0.075 | 1.0 | 1 | 0.165 | 0.134 |
| main | single_cell | 16 | 0 | 1500 | 0.038 ± 0.011 | 0.013 | 0.038 | 1.0 | 1 | 0.066 | 0.105 |
| main | single_cell | 16 | 1 | 1500 | 0.038 ± 0.011 | 0.015 | 0.038 | 1.0 | 1 | 0.108 | 0.128 |
| main | single_cell | 32 | 0 | 1500 | 0.021 ± 0.010 | 0.016 | 0.021 | 1.0 | 1 | 0.079 | 0.116 |
| main | single_cell | 32 | 1 | 1500 | 0.017 ± 0.008 | 0.013 | 0.017 | 1.0 | 1 | 0.083 | 0.112 |
| main | single_cell | 64 | 0 | 1500 | 0.020 ± 0.008 | 0.021 | 0.020 | 1.0 | 1 | 0.085 | 0.115 |
| main | single_cell | 64 | 1 | 1500 | 0.017 ± 0.008 | 0.023 | 0.017 | 1.0 | 1 | 0.100 | 0.122 |
| noshift | learned | 16 | 0 | 1500 | 0.065 ± 0.015 | 0.015 | 0.017 | 22.2 | 44 | 0.298 | 0.222 |
| noshift | learned | 16 | 1 | 1500 | 0.061 ± 0.014 | 0.014 | 0.018 | 28.4 | 54 | 0.343 | 0.271 |
| noshift | oracle | 16 | 0 | 1500 | 0.990 ± 0.006 | 0.018 | 0.014 | 62.9 | 153 | 0.858 | 0.781 |
| noshift | oracle | 16 | 1 | 1500 | 0.995 ± 0.004 | 0.014 | 0.017 | 61.7 | 153 | 0.840 | 0.765 |
| off | memory_off | 4 | 0 | 0 | 0.019 ± 0.009 | — | — | 0.0 | 0 | — | — |
| off | memory_off | 16 | 0 | 0 | 0.021 ± 0.009 | — | — | 0.0 | 0 | — | — |
| off | memory_off | 64 | 0 | 0 | 0.012 ± 0.006 | — | — | 0.0 | 0 | — | — |

## Readings

### R1: DESCRIPTIVE
- N=4: oracle s0 1.000, s1 0.999
- N=8: oracle s0 1.000, s1 1.000
- N=16: oracle s0 1.000, s1 1.000
- N=32: oracle s0 0.999, s1 0.999
- N=64: oracle s0 1.000, s1 1.000

### R2: MET (N* = 4)
- N=4: oracle - single_cell = +0.459

### R3: MET
- N=4 s0: learned 0.882 vs single_cell 0.557; paired gain +0.325 ± 0.035; read+3 paired drop +0.864 ± 0.022 → pass
- N=4 s1: learned 0.926 vs single_cell 0.523; paired gain +0.402 ± 0.033; read+3 paired drop +0.910 ± 0.018 → pass
- N=4: MET
- N=8 s0: learned 0.877 vs single_cell 0.111; paired gain +0.766 ± 0.027; read+3 paired drop +0.862 ± 0.021 → pass
- N=8 s1: learned 0.903 vs single_cell 0.075; paired gain +0.828 ± 0.022; read+3 paired drop +0.890 ± 0.018 → pass
- N=8: MET
- N=16 s0: learned 0.052 vs single_cell 0.038; paired gain +0.014 ± 0.015; read+3 paired drop +0.034 ± 0.014 → fail
- N=16 s1: learned 0.593 vs single_cell 0.038; paired gain +0.555 ± 0.032; read+3 paired drop +0.577 ± 0.032 → pass
- N=16: NOT MET
- N=32 s0: learned 0.021 vs single_cell 0.021; paired gain +0.000 ± 0.012; read+3 paired drop +0.008 ± 0.010 → fail
- N=32 s1: learned 0.021 vs single_cell 0.017; paired gain +0.005 ± 0.012; read+3 paired drop +0.006 ± 0.011 → fail
- N=32: NOT MET
- N=64 s0: learned 0.020 vs single_cell 0.020; paired gain +0.000 ± 0.012; read+3 paired drop -0.002 ± 0.013 → fail
- N=64 s1: learned 0.018 vs single_cell 0.017; paired gain +0.001 ± 0.011; read+3 paired drop -0.002 ± 0.011 → fail
- N=64: NOT MET

### R4: DESCRIPTIVE
- learned/N=4/s0: none 0.882 → bank_derange 0.016
- learned/N=4/s1: none 0.926 → bank_derange 0.020
- learned/N=8/s0: none 0.877 → bank_derange 0.016
- learned/N=8/s1: none 0.903 → bank_derange 0.012
- learned/N=16/s1: none 0.593 → bank_derange 0.016
- oracle/N=4/s0: none 1.000 → bank_derange 0.017
- oracle/N=4/s1: none 0.999 → bank_derange 0.016
- oracle/N=8/s0: none 1.000 → bank_derange 0.018
- oracle/N=8/s1: none 1.000 → bank_derange 0.013
- oracle/N=16/s0: none 1.000 → bank_derange 0.015
- oracle/N=16/s1: none 1.000 → bank_derange 0.013
- oracle/N=32/s0: none 0.999 → bank_derange 0.016
- oracle/N=32/s1: none 0.999 → bank_derange 0.012
- oracle/N=64/s0: none 1.000 → bank_derange 0.016
- oracle/N=64/s1: none 1.000 → bank_derange 0.015
- random_fixed/N=4/s0: none 0.079 → bank_derange 0.014
- random_fixed/N=4/s1: none 0.100 → bank_derange 0.012
- single_cell/N=4/s0: none 0.557 → bank_derange 0.014
- single_cell/N=4/s1: none 0.523 → bank_derange 0.012
- single_cell/N=8/s0: none 0.111 → bank_derange 0.011
- single_cell/N=8/s1: none 0.075 → bank_derange 0.015

