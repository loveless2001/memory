# PREPROBE.md execution plan (E1 + E2)

Brief: /PREPROBE.md. Deliverable: /PREPROBE-REPORT.md + raw artifacts.
Data: memsub-artifacts:/compactor-gate-labels (98,355 relabeled items, t=1024
arm = tag single-t1024-T8k), corpus (40k docs), checkpoints.

## Phases — ALL COMPLETE (2026-07-17)

- [x] P1 E2 surface pass (40k docs / 908M tokens; 98,354 items featured)
- [x] P2 E2 sample: 15,034 y=1 + 15,034 matched y=0 (10,613 same-doc)
- [x] P3 E2 fact-type pass (30,068 classified)
- [x] P4 E2 analysis: no univariate ≥ 0.60; c0 AUC 0.564 [0.553, 0.575]
- [x] P5 E1 sample: 2,000 stratified, tercile bounds (−5.315, −4.073)
- [x] P6 Train B seed51234: final loss 0.252 (A: 0.239), ~95 min, ≈$53
- [x] P7 Relabels A2/B/C (A2 = added protocol-determinism control)
- [x] P8 κ(A↔A2)=1.000, κ(A↔B)=0.745 → CONTENT-STRUCTURED,
      κ(A↔C)=0.455. Report: /PREPROBE-REPORT.md

## Key decisions
- B trains under the LEGACY (pre-f214c0f) KL objective via explicit flag:
  A was trained pre-fix; seed must be the only difference. ADDENDUM-M35's
  "future training uses corrected objective" applies to production, not to
  a controlled replication.
- Relabels run on H100 (same GPU class as the A relabel) to avoid
  cross-arch numeric drift contaminating label agreement.
- κ also reported at natural prevalence (stratified sample reweighted) since
  κ is prevalence-sensitive; brief's stratified-sample κ stays primary.
