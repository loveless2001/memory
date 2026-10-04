# ContextPolicy v2 — stopped at cache preflight

**Verdict: preflight_failed; no corpus training started.** The registered
exact-token cache gate failed on one of 40 development probes. This is a
runtime-validation result, not an action-policy accuracy result.

| Check | Result |
|---|---|
| Actual reader | Qwen3-4B-Instruct-2507, pinned revision, bf16 SDPA |
| Device | NVIDIA H100 80GB HBM3 |
| LoRA trainable parameters | 5,898,240 |
| Frozen original parameters | 4,022,468,096 |
| Disposable gradient-check updates | 2; finite loss and adapter gradients |
| Greedy continuation equality | 39 / 40 |
| Next-token equality at tested append boundaries | 120 / 120 |
| Actual chat-template prefix checks | Passed for two tool appends per probe |
| Silently disabled adapter rejected | Passed |
| Function elapsed time | 68.21 seconds |
| Modal reported app cost | $0.09228470 as of 2026-09-09T19:04:08.202868+00:00 |
| Local CPU suite after harness fix | 19 passed in 3.95 seconds |

## The mismatch

Probe `cache-probe-1-5` asks for a supplier contract price absent from the
history. Both paths abstained, with different wording:

- Cached: “The supplier contract price was not mentioned in the discussion.”
- Fresh: “The supplier contract price was not mentioned in the provided information.”

The first difference is at zero-based generated-token index 9, before EOS.
There was no observed change to the factual conclusion in this one probe.
The gate requires exact greedy sequences, so semantic similarity does not
convert this result into a pass. The test does not distinguish bf16/kernel
rounding from another numerical/runtime issue; that needs a focused diagnostic.
Maximum absolute vocabulary-logit delta at tested append boundaries was 2.125
across the suite, and 0.671875 for the failing probe. These maxima are not
measurements of the top-token margin at the first divergent decode step.

The original comparison loop continued after one path emitted EOS if the
other had not yet ended. The local harness now stops each path independently,
with a regression test. The raw outputs are preserved; trimming each at its
first EOS still yields the same failed comparison. No GPU rerun of that fix
was submitted. The bounded probes generate at most 16 tokens, so agreement
on the other probes does not certify unrestricted long answers.

## Provenance and scope

- [Modal app](https://modal.com/apps/syntracts/main/ap-luILv5sw5X3OtVyWwy2elf)
- Function call: `fc-01M23RNHK5B6YVCCQRMG7BNX2E`.
- Source binding: `c718e3f763256ed987acc3ab8465ef25e9eb33e76924c50cef944dbdc5050435`.
- All eight remote artifact hashes and seven archived source-file hashes verified.
- The original code/config/design are in `source-snapshot/`; current files include
  the later EOS fix and failed-gate status. `verification.json` records checks.
- The previous ContextGate v1 source files still match their completed-run manifest.
- The disposable adapter is a two-update gradient probe, not a trained action policy.
- No training corpus, counterfactual labels, external benchmark answers, or
  paid judging were generated. No automatic retry occurred.

The benchmark/evaluator and embedding revisions were pinned before preflight,
but full data acquisition, corpus realization/audit, trainer integration, and
independent evaluation remain pending. The local training-support module
implements assistant-only masking and separate normalized routing loss;
it has not been used for corpus training.

Next technical step: compare the first divergent same-prefix logits under
controlled precision and attention implementations, preserving the current
failed result. Corpus training remains stopped until cache validation passes.
