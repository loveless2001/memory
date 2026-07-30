# MergeCert Q1 — Moderate-Ratio Placement

Private to Tyler and Kevin.

Local/private report only. Transmission is not recorded. No public artifact is authorized.

## Settled 0.90 result

The parent P0 result remains settled and was not rerun by this addendum.

| settled 0.90 check | value |
|---|---:|
| merge lost given prior-correct | 0.873626 |
| eviction lost given prior-correct | 0.824176 |
| merge - eviction, 95% CI | +0.0495 [+0.0055, +0.0939] |
| registered P0.3 direction gate | FAIL |

## Q1 — Moderate-ratio placement

| matched Q1 arm | agg KL | agg accΔ | pointwise lost|prior |
|---|---:|---:|---:|
| eviction 0.25 | 0.0303 | -0.029 | 0.550 |
| MERGE 0.25 | 0.0360 | -0.075 | 0.400 |
| eviction 0.40 | 0.0335 | -0.071 | 0.650 |
| MERGE 0.40 | 0.0591 | -0.133 | 0.425 |
| zero-compression control | 0.0000 | +0.000 | 0.000 |

Per-document matched physical budgets preserve the exact archived M1 population. 4,096-token source/model inputs retain 3,072 tokens at 0.25 and 2,458 tokens at 0.40. Shorter archived contexts use their measured matched budgets.

### Historical context — not directly budget/population matched

These latest n=60 reference rows use different populations and approximately 50% compression. They are historical context, not Q1-matched comparators.

| reference regime | population / budget note | n | agg KL | agg accΔ | pointwise lost|prior |
|---|---|---:|---:|---:|---:|
| frozen full-recipe d1 (n=60) | different n=60 population; ~50% compression | 60 | 0.2820 | +0.1019 | 0.210 |
| clean unfrozen d1 (n=60) | clean held-out n=60 population; 49.9% compression | 60 | 0.1281 | +0.0536 | 0.050 |

| ratio | merge - eviction metric | paired estimate and 95% CI |
|---:|---|---:|
| 0.25 | lost|prior | -0.1500 [-0.3500, +0.0500] |
| 0.25 | agg KL | +0.0057 [-0.0057, +0.0173] |
| 0.25 | agg accΔ | -0.0458 [-0.0958, +0.0000] |
| 0.40 | lost|prior | -0.2250 [-0.4000, -0.0500] |
| 0.40 | agg KL | +0.0256 [+0.0079, +0.0496] |
| 0.40 | agg accΔ | -0.0625 [-0.1750, +0.0458] |

## Per-domain slices

| domain | arm | documents | agg probes | needle probes | agg KL | agg accΔ | lost|prior |
|---|---|---:|---:|---:|---:|---:|---:|
| financial | zero-compression control | 5 | 15 | 7 | 0.0000 | +0.000 | 0.000 |
| financial | eviction 0.25 | 5 | 15 | 7 | 0.0276 | +0.000 | 0.900 |
| financial | eviction 0.40 | 5 | 15 | 7 | 0.0276 | -0.200 | 0.900 |
| financial | MERGE 0.25 | 5 | 15 | 7 | 0.0253 | +0.000 | 0.500 |
| financial | MERGE 0.40 | 5 | 15 | 7 | 0.0392 | -0.333 | 0.400 |
| legal | zero-compression control | 5 | 15 | 5 | 0.0000 | +0.000 | 0.000 |
| legal | eviction 0.25 | 5 | 15 | 5 | 0.0609 | +0.000 | 0.200 |
| legal | eviction 0.40 | 5 | 15 | 5 | 0.0646 | +0.000 | 0.600 |
| legal | MERGE 0.25 | 5 | 15 | 5 | 0.0764 | -0.117 | 0.200 |
| legal | MERGE 0.40 | 5 | 15 | 5 | 0.1145 | -0.067 | 0.200 |
| code | zero-compression control | 5 | 9 | 5 | 0.0000 | +0.000 | 0.000 |
| code | eviction 0.25 | 5 | 9 | 5 | 0.0065 | +0.000 | 0.800 |
| code | eviction 0.40 | 5 | 9 | 5 | 0.0143 | +0.000 | 0.800 |
| code | MERGE 0.25 | 5 | 9 | 5 | 0.0154 | +0.000 | 0.600 |
| code | MERGE 0.40 | 5 | 9 | 5 | 0.0357 | +0.050 | 0.800 |
| literature | zero-compression control | 5 | 15 | 8 | 0.0000 | +0.000 | 0.000 |
| literature | eviction 0.25 | 5 | 15 | 8 | 0.0262 | -0.117 | 0.300 |
| literature | eviction 0.40 | 5 | 15 | 8 | 0.0274 | -0.083 | 0.300 |
| literature | MERGE 0.25 | 5 | 15 | 8 | 0.0269 | -0.183 | 0.300 |
| literature | MERGE 0.40 | 5 | 15 | 8 | 0.0467 | -0.183 | 0.300 |

## Registered readings

R1 pointwise: merge CI-below eviction on lost|prior at either ratio → the preservation instinct holds at moderate ratios; scoped spectrum row earned ("blend-preserving at moderate ratios, collapsing at extreme"), §13.7 note upgraded accordingly.

R2 pointwise: CI-overlapping or worse (the E2 interference prediction — averaging manufactures confusable-sibling blending) → placement closes negative on the needle axis at all ratios; the theory's "merging is structurally worst-case for bindings" reading is confirmed at deployment-relevant compression.

R3 aggregation: independent of R1/R2, report where merge KL/accΔ lands relative to eviction — a merge that loses needles but wins aggregation is STILL a coherent scoped result (gist tier behind a gate), and the two-axis protocol exists precisely to say so without blending.

Measured verdicts: R1 and aggregation-negative.

## Conditional Q2/Q3

The registered Q1 trigger authorized amended variable-context Q2/Q3. It preserves the original 30,847-item population and uses per-item matched physical budgets rather than the failed fixed-context protocol.

### Amended variable-context Q2 — Routability

| arm | merge 0.25 test AUC [95% CI] | merge 0.40 test AUC [95% CI] | pooled test AUC [95% CI] |
|---|---:|---:|---:|
| surface / c0 refit | 0.5537 [0.5416, 0.5655] | 0.5424 [0.5299, 0.5547] | 0.6179 [0.6085, 0.6276] |
| merge mechanics refit | 0.6552 [0.6449, 0.6664] | 0.5890 [0.5773, 0.6009] | 0.6555 [0.6468, 0.6645] |
| shadow gate zero-shot | 0.6779 [0.6675, 0.6897] | 0.6180 [0.6076, 0.6292] | 0.6481 [0.6389, 0.6572] |
| shadow gate refit | 0.5315 [0.5178, 0.5440] | 0.5932 [0.5822, 0.6044] | 0.6265 [0.6169, 0.6359] |
| sink monitor compactor to merge | 0.6472 [0.6347, 0.6593] | 0.5845 [0.5731, 0.5966] | 0.6183 [0.6081, 0.6281] |
| sink monitor eviction to merge | 0.5514 [0.5391, 0.5635] | 0.5104 [0.4985, 0.5227] | 0.5318 [0.5215, 0.5418] |
| sink monitor merge refit | 0.6258 [0.6130, 0.6382] | 0.5534 [0.5413, 0.5657] | 0.6894 [0.6804, 0.6980] |
| residual best-layer linear | 0.8373 [0.8288, 0.8454] | 0.7682 [0.7581, 0.7776] | 0.8153 [0.8087, 0.8223] |
| residual best-layer MLP | 0.8558 [0.8483, 0.8629] | 0.7934 [0.7844, 0.8027] | 0.8352 [0.8284, 0.8416] |

Merged-loss routability falls between the two registered anchor readings (mechanics 0.622, residual 0.825); retain the measured placement.

### F5 fifth-regime row

| F5 fifth-regime row | merge 0.25 AUC [95% CI] | merge 0.40 AUC [95% CI] |
|---|---:|---:|
| compactor to merge zero-shot | 0.6472 [0.6347, 0.6593] | 0.5845 [0.5731, 0.5966] |
| eviction to merge zero-shot | 0.5514 [0.5391, 0.5635] | 0.5104 [0.4985, 0.5227] |
| merge refit | 0.6258 [0.6130, 0.6382] | 0.5534 [0.5413, 0.5657] |

### Amended variable-context Q3 — Fragility

| reference regime | merge failure rate | reference failure rate | raw agreement | Cohen kappa | merge-conditioned nesting | intersection / merge failures | novel merge failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 0.5435 | 0.4995 | 0.6580 | 0.3161 | 0.6449 | 701 / 1087 | 386 |
| B | 0.5435 | 0.4180 | 0.6225 | 0.2556 | 0.5373 | 584 / 1087 | 503 |
| FR | 0.5435 | 0.3210 | 0.5995 | 0.2232 | 0.4269 | 464 / 1087 | 623 |
| E1F | 0.5435 | 0.1720 | 0.5565 | 0.1609 | 0.2502 | 272 / 1087 | 815 |

Fragility is reported marginal-aware: kappa measures agreement beyond the two observed base rates, while nesting conditions only on merge failures. The novel-merge count therefore identifies the mechanism-specific minority without treating prevalence shrinkage as disagreement.

## Compute provenance

| phase | compute | measured seconds | actual cost USD | billing source | app IDs |
|---|---|---:|---:|---|---|
| Q1 | H100 | 262.1 | 0.33 | Modal billing report 2026-07-30 for apps ap-Bx0LRrGGZ0yUchiepNVrtV, ap-IqcTqya9JbXUoI57uApnwU, ap-amdd5k9Ybxoxv1d8c3vbon, ap-FS1Y8Y3bcazBqzMybadmyo, ap-f53tWxXjsQH95pN0uZzxQx and ap-bnyT0P9ay00aSaBC0u4gyc | ap-Bx0LRrGGZ0yUchiepNVrtV, ap-IqcTqya9JbXUoI57uApnwU, ap-amdd5k9Ybxoxv1d8c3vbon, ap-FS1Y8Y3bcazBqzMybadmyo, ap-f53tWxXjsQH95pN0uZzxQx, ap-bnyT0P9ay00aSaBC0u4gyc |
| Q2/Q3 | H100 + L4 | 25302.2 | 30.81 | Modal billing report 2026-07-30 for apps ap-Oxquib97yXgc1yG3xQ5UpQ, ap-vl15qY3btFGWZEFMILacJU, ap-94yLmlHzYzxS6y44wZocc8, ap-OxxQC7S1tcsRvxqu9DunXo, ap-YD3QbLT86MgEHO6pvmZOvA, ap-pXurmOrK1qTY1XcwqIHqtm, ap-kfNyO5Unf3vtZsQGhhvKXL, ap-ViyPfkrIVHuefF33mxvIVD, ap-1onFbAA3F2jlnhXdQKiSQU, ap-fPaPltzBmeC1WEATZ4j6a4 and ap-Jd8Jv9M9ENsX1Sbwy5IVJ7 | ap-Oxquib97yXgc1yG3xQ5UpQ, ap-vl15qY3btFGWZEFMILacJU, ap-94yLmlHzYzxS6y44wZocc8, ap-OxxQC7S1tcsRvxqu9DunXo, ap-YD3QbLT86MgEHO6pvmZOvA, ap-pXurmOrK1qTY1XcwqIHqtm, ap-kfNyO5Unf3vtZsQGhhvKXL, ap-ViyPfkrIVHuefF33mxvIVD, ap-1onFbAA3F2jlnhXdQKiSQU, ap-fPaPltzBmeC1WEATZ4j6a4, ap-Jd8Jv9M9ENsX1Sbwy5IVJ7 |
| total | - | - | 31.14 | registered ceiling $45 | - |

## For the KV-Merge README

The registered 0.90 result remains negative for this exact port and house fingerprint.

At moderate compression, merge earns a scoped pointwise row at 0.40; the 0.25 pointwise interval does not separate. It also does not earn the aggregation axis.

Measured favorable axis: 0.40 lost-prior.

## For the spec

Draft §13.7 note: record R1 and aggregation-negative for the pinned Qwen3 fingerprint and the measured 0.25/0.40 protocol. Keep aggregation and pointwise axes separate.

## Limitations

- One pinned house model fingerprint.

- Two registered moderate ratios; no sweep or tuning.

- The 0.90 result is imported from the settled parent evidence.

- Scientific placement only; this is not a deployment certification.

- No hybrid or anchor variant was run.
