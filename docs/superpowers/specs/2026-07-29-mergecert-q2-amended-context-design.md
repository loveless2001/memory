# MergeCert Q2 Amended Context Design

**Date:** 2026-07-29

**Status:** Design approved; written-spec review pending

**Authority:** The user's selected MergeCert Q2 protocol option 2. The
settled amendment artifact defined below is the sole new Q2 protocol
authority. The unchanged `q1-trigger.json` remains necessary authorization,
but it is not the Q2 amendment.

## Objective

Run the existing 30,847-item Q2 population without padding, skipping,
replacement, label changes, or silent fixed-context assumptions. Long
documents retain the exact registered 4,096-token behavior. Documents shorter
than 4,096 pinned-tokenizer tokens use their complete actual source window,
with contiguous eviction and merge matched to the measured physical cache
budget for each item and ratio.

This design is local implementation work only. It authorizes no upload, pilot,
fleet, probe, or other remote mutation.

## Chosen architecture

A shared pure accounting module defines the amended context window, budget
equations, strict schemas, and array validation. The capture runner measures
the actual cache mutation and supplies those measurements to the shared
validator. The probe runner, Q2 analyzer, Q3 analyzer, and final report
validator consume the same contract.

Rejected alternatives:

- Duplicating validation in each consumer would make it possible for capture,
  probes, analysis, and reporting to accept different equations.
- A separate accounting sidecar would leave capture chunks without their own
  complete per-item accounting and weaken artifact-level validation.

## Settled authority and namespaces

The tracked artifact
`plans/260728-mergecert-q1/q2-amendment.json` is canonical JSON and records
the date, status, population, ratios, context rules, budget equations,
context-mechanics version, and namespace version. Every amended artifact
records both its exact payload and SHA-256.

The amended remote root is:

```text
/artifacts/mergecert/q2-amended-v2
```

It contains a new `pilot-amended-v2` namespace, new
`full-amended-v2-slice-00` through `full-amended-v2-slice-07` namespaces,
and amended capture summary, probe inputs, routability output, and score
output. The old `/artifacts/mergecert/q2/pilot-q1-triggered` and
`/artifacts/mergecert/q2/full-slice-*` artifacts remain immutable failed or
legacy evidence. No amended gate may accept, resume, overwrite, or derive
authorization from them.

The amended pilot verdict version, state schema, capture schema, summary
schema, probe schema, analyzer output, and Q3 output are all versioned. The
new pilot verdict binds the amendment payload/hash, exact Q1 trigger/hash,
source manifest/hash, state/hash, chunk hashes/audits, and compatibility
fingerprint.

## Deterministic context window

For each registered manifest row:

```text
chunk_absolute = integer encoded in item_id before the final suffix
preferred_start = chunk_absolute - chunk_rel_start
maximum_start = max(source_document_token_count - 4096, 0)
source_context_start = clamp(preferred_start, 0, maximum_start)
source_context_end = min(source_context_start + 4096,
                         source_document_token_count)
source_context_token_count = source_context_end - source_context_start
model_input_token_count = source_context_token_count
source_chunk_context_start = chunk_absolute - source_context_start
```

The tokenizer is the compatibility-fingerprint-pinned tokenizer. The model
receives those token IDs directly, so source-context and model-input counts
are deterministically comparable. Every count must be a non-boolean integer,
and every context must contain more than the four pinned sink tokens.

For documents with at least 4,096 tokens, this is byte-for-byte the previous
Q2 context selection and yields exactly 4,096 model-input tokens. For shorter
documents it selects the complete document without padding.

## Matched physical budget

For each actual context and each ratio in exactly `{0.25, 0.40}`:

```text
requested_evicted_token_count =
    floor(source_context_token_count * ratio)
eviction_source_start = 4
eviction_source_end =
    eviction_source_start + requested_evicted_token_count
physical_before_count = full_cache.physical_length
physical_removed_count =
    eviction_cache.evict_logical_range(eviction_source_start,
                                       eviction_source_end)
physical_after_count = eviction_cache.physical_length
retained_token_count = physical_after_count
merge_target_retained = retained_token_count
```

The runner rejects any mismatch among:

```text
eviction_source_end - eviction_source_start
    == requested_evicted_token_count
physical_before_count == model_input_token_count
physical_before_count - physical_after_count
    == physical_removed_count
physical_removed_count == requested_evicted_token_count
retained_token_count == physical_after_count
merge_target_retained == retained_token_count
```

Merge is built from the actual model-input length with the smallest effective
fraction that reproduces `merge_target_retained` exactly. The resulting plan
must report that exact retained target.

At 4,096 tokens, the amended 0.25 and 0.40 plans reproduce respectively:

```text
ratio  requested  retained  recent_start
0.25   1024       3072      2562
0.40   1638       2458      2869
```

Local comparison confirms the target, recent start, and complete merge block
layout are identical to the pre-amendment `build_merge_plan(4096, ratio)`
behavior.

## Per-item accounting contract

Every ratio row in each capture NPZ records:

- `context_mechanics_version`;
- `source_document_token_count`;
- `source_context_start`, `source_context_end`, and
  `source_context_token_count`;
- `source_chunk_token_start` and `source_chunk_context_start`;
- `model_input_token_count`;
- `eviction_source_start`, `eviction_source_end`, and
  `requested_evicted_token_count`;
- `physical_before_count`, `physical_after_count`, and
  `physical_removed_count`;
- `retained_token_count` and `merge_target_retained`;
- `merge_recent_start`;
- `ratio`.

The shared validator rejects boolean integers, non-finite or unregistered
ratios, shifted windows or eviction ranges, impossible counts, inconsistent
physical equations, mismatched merge targets, and fixed-4,096 derivations for
short documents. It also recomputes each canonical context start from the
registered row anchor and recorded source-document length.

State chunk records bind the accounting audit and canonical accounting hash
for each NPZ. Frozen summary chunk records preserve those bindings and verify
exact two-ratio coverage of all 30,847 item IDs. This hash chain makes the
complete per-item accounting in the NPZs part of both state and summary
provenance without duplicating tens of thousands of rows into JSON.

## Downstream data flow

The amended probe gate requires the amended summary path, namespace version,
context-mechanics version, amendment payload/hash, Q1 trigger/hash, and full
30,847-item coverage. It validates every capture chunk through the shared
accounting validator before assembly.

Probe score NPZs propagate the complete flattened per-item accounting for both
ratios. The mechanics design uses each row's actual `merge_recent_start` and
`source_chunk_context_start`; it contains no 4,096 constant for short rows.
Routability JSON binds the score hash, capture summary hash, amendment
payload/hash, Q1 trigger/hash, and shared accounting audit.

The local Q2 analyzer independently loads the tracked amendment artifact,
verifies its hash and payload against both routability JSON and score NPZ,
validates all flattened accounting equations, and emits the same amendment
binding in its verdict. Q3 requires identical amendment bindings across the
Q2 verdict and score NPZ before selecting the registered ratio-0.40 E1 rows,
and writes that binding into its result.

The final Q1 report validator requires the conditional record, Q2 verdict,
Q3 result, and tracked amendment artifact to agree on the same payload/hash.
Missing, old, or drifted amendment evidence fails closed. The renderer labels
the conditional result as amended variable-context Q2 rather than the
original fixed-4,096 Q2.

## Execution gate

Local implementation and tests do not authorize compute. A future remote
sequence requires fresh explicit approval and exactly:

1. one new 16-item `pilot-amended-v2` run, even if all selected rows are long;
2. independent validation and review of its amended verdict;
3. only after that reviewed pass, one new eight-slice amended fleet covering
   exactly the same 30,847 registered item IDs;
4. capture freeze and probes only after all amended slices pass.

Old pilot verdicts and old fixed-context slice states cannot satisfy any new
gate.

## Error handling

Fail before checkpoint or downstream use on any of:

- missing or drifted amendment artifact/hash;
- missing or altered Q1 trigger/hash;
- source document, manifest, item-order, or compatibility drift;
- nondeterministic or invalid context anchor/window;
- context length at or below the sink prefix;
- shifted eviction range or physical accounting mismatch;
- merge retained target or recent-start mismatch;
- old namespace, pilot verdict, state, summary, probe output, or score input;
- incomplete or duplicate 30,847-item ratio coverage;
- fixed-4,096 mechanics applied to a short row.

No failure path pads, skips, substitutes, deletes, resumes legacy evidence, or
weakens a gate.

## Verification

RED regressions must include the three proven `code/00130` item IDs at 4,073
tokens, a long 4,096-token context, and mutations for:

- shifted context and eviction ranges;
- booleans and impossible counts;
- wrong physical removal or merge target;
- fixed-4,096 recent-start assumptions on short rows;
- old pilot/state/namespace acceptance;
- amendment payload/hash drift at capture, probe, Q2, Q3, and report layers;
- manifest item-ID or count drift.

Completion requires focused capture/probe/Q2/Q3/report tests, complete pinned
offline tests, Python compilation, exact unchanged Q1 trigger SHA-256,
amendment hash verification, `git diff --check`, and a clean tracked status.
