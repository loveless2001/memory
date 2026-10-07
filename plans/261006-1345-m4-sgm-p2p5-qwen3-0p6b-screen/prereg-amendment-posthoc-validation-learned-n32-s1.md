# P2.5 PK campaign: POST-HOC validation amendment, learned-n32-s1 (protocol deviation)

Status: user-approved option B (user 21710, 2026-10-07 22:04 +07). Proposal claude 21700/21702; scope codex
21701/21703/21712. Written AFTER training ended and after the failure was seen, so it is post-hoc. It replaces no
frozen file: prereg v0.2, Amendment PK, grid, registry, schema, supplement, v5/v6 and proof bytes are unchanged.

## Original outcome (kept)
- learned-n32-s1 was FAILED by the slot supervisor's output validation:
  `output schema: layer-normalised key L{L}/k_proj has inconsistent schemas`.
- Prereg + supplement step 6 require all 18 cells COMPLETE and valid, so the ORIGINAL campaign outcome is
  "unavailable" at N32 AND N16 (codex 21706). Every amended reading below carries this original reading next to it.

## Diagnosis (claude 21700, confirmed codex 21703)
- 51 null leaves, all `grad_norm.L20/{k_proj,value,beta}` on 17/150 logged training rows (first step 50), with zero
  update norms there. memsub `_group_norms` documents None as "no gradient reached the group". s0 has none.
- Every other validator stage passes; the 7 outputs match done.json; the terminal checkpoint (gen 30, step 1500)
  matches its acknowledged chain.
- Why no gradient reached L20's write path on those batches, and whether it matters scientifically, is
  UNDETERMINED. This amendment is not evidence that the run learned well or that the gap is harmless.

## The amendment (exact scope)
Spec: `configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json` (frozen, in the analysis manifest).
Logic: `scripts/sgm-p2p5-pk-posthoc-validation-amendment.py` (analysis layer; memsub unchanged).
1. ONE cell: learned-n32-s1. Its record must be FAILED with the exact original reason, and must match exactly:
   state.json sha d4996651…, done.json sha 33a3dafb…, the seven output hashes, and terminal checkpoint
   gen-30-step1500.pt sha 38982aab…. No COMPLETE is inferred and the FAILED record is never rewritten.
2. The ORIGINAL validator with the frozen schema must return exactly the original failure. WITHOUT the schema
   stage it must return valid (all other checks kept).
3. Exception: null is accepted ONLY at the 51 listed (step, `grad_norm` key) leaves, each typed "num" by the
   frozen schema. The field `grad_norm` is fixed in code. update_norm and every other field get no exception.
   The exact null set must equal the list.
4. With only those leaves typed as numbers (a private copy, used only to compute the schema), the ORIGINAL schema
   functions must reproduce the frozen schema, layer coverage included.
5. Any other FAILED/LOST cell, or this cell failing any check above, keeps the readings unavailable.

## Gates and labels
- Local spawn (readings runner): it needs the write-once re-validation record
  `pk-campaign-posthoc-amendment/learned-n32-s1-revalidation-record.json` to say `amended_valid`, bound to the
  spec sha. slots_ready accepts the spec cell ONLY when it is FAILED with the original reason.
- Readings run: it binds first under the ORIGINAL gate (expected: `unavailable: learned-n32-s1: state FAILED`),
  then under the amended gate, which re-validates the cell on the volume itself.
- `readings.json`: `campaign_label = "post-hoc amended"`. EVERY N gets `label = "post-hoc amended"` and an
  `original_reading`. The `posthoc_amendment` block holds the original gate and the spec sha.
- Unchanged: exactly one readings run; reserved population 9_600_011+s; start/end dependency binding; parity;
  two-phase oracle order; per-N gating; the decision table; the controller deadline. The latest readings spawn
  stays 17:06:30.652974 UTC (codex 21706).
