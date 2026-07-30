# MergeCert — Attention-Weighted KV Merge Placement

This scientific placement run evaluates the method at its best: the house Qwen3-4B-Instruct-2507 fingerprint, real accumulated attention, proper paired statistics, and exactly matched retained-vector budgets. It evaluates the method rather than reproducing the source repository's evaluation, and every pre-registered outcome is reportable.

## P0 — Port and verification

The port replaces the source approximation with real accumulated causal attention reduced from query heads to their grouped KV heads. The sink addition pins logical positions 0-3 identically for merge, eviction, and StreamingLLM comparators. Recent KV stays exact; old-region blocks become per-layer, per-KV-head weighted K and V averages. Retained budgets are exactly 3,072, 2,458, and 410 vectors at 0.25, 0.40, and 0.90.

| registered check | result | evidence |
|---|---:|---|
| P0.3 merge lost given prior-correct | 0.8736 | 200-item house pointwise metric |
| P0.3 eviction lost given prior-correct | 0.8242 | same items and retained budget |
| paired merge minus eviction | +0.0495 [+0.0055, +0.0939] | document-cluster bootstrap 95% CI |
| merge / eviction mean continuation KL | 0.3804 / 0.3153 | fixed continuation |
| merge exact-slot Jaccard vs StreamingLLM | 0.5049 | 203 non-singleton blocks |
| merge / StreamingLLM prediction equality | 0.8250 | same 200 items |
| aligned exact / physical max absolute KV difference | 0 / 152 | exact-slot preservation and non-degeneracy |

P0.3 direction gate: FAIL. P0.4 non-degeneracy gate: PASS. Real-attention validity: PASS.

## Registered stop

P0.3 did not reproduce the registered qualitative direction. Failed registered check: P0.3 direction. Q1-Q3 were not launched, as required. This is a negative placement result for this port and fingerprint; no tuning or alternate model was attempted.

## Compute actuals

| phase | compute | measured seconds | actual cost USD | source |
|---|---|---:|---:|---|
| P0 | H100 | 306.1 | 0.38 | Modal billing report 2026-07-27 for apps ap-LhQ8XuapnFgxvOgxih3tr3, ap-n8C84UMNCvqC8Mc5bIM3c5, and ap-Vm2RcWMIGSeIN2ykNdSyxB |
| total | - | - | 0.38 | measured campaign actual |

## Limitations

- One house model fingerprint only; this is not a cross-model comparison.

- One registered ratio grid; no hyperparameter sweep.

- The fixed continuation KL is a short smoothness probe, not a long-horizon generation guarantee.

- Diagnostic probe refits measure routability; they do not train or modify the merge policy or base model.

- This is scientific placement only, not a deployment or L3-default certification.

## For the KV-Merge README

Supported claim: on the pinned house fingerprint and registered 90% point, the real-attention port did not establish graceful degradation over matched eviction under the pre-registered pointwise gate.

Not supported: graceful-degradation, deployment, cross-model, or source-evaluation reproduction claims. The result localizes the finding to this exact port and protocol and does not imply that other implementations cannot work.

## For the spec

Draft §13.7 note: attention-weighted merge was evaluated as a candidate fourth training-free regime point, but the registered direction gate failed. Record it as a measured negative placement and do not add a positive regime claim.
