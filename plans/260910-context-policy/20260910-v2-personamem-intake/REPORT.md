# PersonaMem-v2 intake: candidate fails grounding admission

**No LoRA training launched. No additional GPU or judge charges incurred.**

The existing-history candidate removes the need to generate dialogue, but its
unchanged reference answers fail this experiment's admission rule. Four
confirmed problem cases in the predetermined 50-question sample leave at most
46 sound cases, below the required 48. This is an admission decision, not a
measured dataset-wide error rate or a negative result about learned retrieval.

## Acquired and checked

Source: [PersonaMem-v2 text training release](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/tree/ed956dea41521fc4499acbc63f966e0fd3c053ba),
revision `ed956dea41521fc4499acbc63f966e0fd3c053ba`, CC-BY-4.0.
The training CSV contains **18,549 rows and 800 personas**, with 6–39 queries
per persona. Its SHA-256 matches the release's LFS object ID:
`62abb042f529818a22be4ced84b683364f000af68608008c20186527740276d6`.
The pinned README and schema were also acquired successfully.

Ten personas and five questions per persona were selected by fixed SHA-256
rankings before inspecting their examples. All ten are in the prospective
training partition. Their ten history files were verified against the pinned
release's remote object IDs. No PersonaMem validation or benchmark CSV was
acquired or scored. One separate history was inspected to establish its schema
before sample selection; it is not part of the 50-case audit.

All ten sampled histories contain a system message exposing the full synthetic
persona. The new intake module removes every system message and whitelists
only `role` and `content` from user/assistant turns. Reader queries are parsed
from the release's serialized message field; profiles, preferences, answers,
snippets, ownership labels, and update flags remain private. The reader pack
is explicitly marked **inadmissible for training**.

After system-message removal, the histories contain **29,904–32,984 tokens**
under the pinned Qwen tokenizer. Those counts include chat-template tokens.
The original CSV token counts use a different accounting convention.

## Grounding failures

Indices below are zero-based CSV data-row indices, excluding the header.
Visible turn indices in the evidence artifact exclude system messages.

| Row | Persona | Confirmed problem |
|---|---|---|
| 4266 | 424 | Reference reuses a basketball wrist-fracture history after the user explicitly asks to forget it. |
| 1415 | 149 | Reference asserts a weekend-nap preference after the user explicitly asks to forget it. |
| 4353 | 264 | Cited dialogue describes wrist stiffness; the reference asserts prior wrist surgery that the visible history does not establish. |
| 12697 | 531 | Cited dialogue concerns workplace recognition; the reference introduces an unsupported childhood comparison with a brother's academic achievements. |

The two withdrawal cases are present later in the same full chronological
history supplied to every question. Their current queries do not restore the
withdrawn details. The unsupported-detail cases were checked against their
annotated spans and targeted searches over the full visible histories.

All 50 selected query/reference/snippet annotations were screened by Codex.
This is qualitative source inspection, not an independent human audit. The
remaining 46 cases are **not certified sound**; no 46/50 accuracy or pass rate
is claimed. Four decisive failures suffice to reject unchanged admission.
[Grounding evidence and limitations](grounding-audit.json).

## Structural findings are separate

46/50 snippets match contiguous visible turns after whitespace normalization.
Three unmatched snippets concern synthetic private-identifier examples; the
fourth has a matching withdrawal request but a different/truncated final
assistant response. These four span mismatches were **not** counted as the
four semantic failures above. Missing full-span matches do not alone establish
that a question or its answer is wrong.

No current query exactly duplicates a history turn. One exact assistant turn
is shared by two sampled personas. This checks only the ten downloaded
histories; source overlap across all prospective train/validation/test groups
has not been certified. [Structural audit](structure-audit.json),
[token counts](token-lengths.json).

## Implementation and next boundary

The [intake module](../../../experiments/context_policy/personamem.py) verifies
the pinned CSV, enforces one safe history path per persona, isolates reader
fields, checks support spans, and reproduces sample selection. A local audit
pack contains ten sanitized histories and 50 queries; source annotations are
stored separately under ignored `data/context-policy/personamem-v2/`.

All **28** cache, training-loss, corpus-contract, and intake tests pass
(5.51 seconds). Syntax and whitespace checks pass, and ContextGate v1 sources
still match their completed-run manifest. See [verification](verification.json)
for source hashes and the zero-new-run record.

Do not train on the unchanged references, restore the hidden system persona,
or truncate each history using private answer metadata to evade contradictions.
A usable revision needs reference answers and evidence spans rebuilt from
visible dialogue with its latest instructions, followed by a fresh admission
sample. Query-blind notes, useful-action labels, an independent free-form
judge, and the full training loop remain pending. No further data substitution
or paid run was started.

The prior FP32 cache result remains 40/40. LongMemEval-S remains held out, with
the original external advancement rule unassessable because its source graph
has one connected component. This intake does not amend that rule or adopt a
replacement external benchmark.
