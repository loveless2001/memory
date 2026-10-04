# Frozen Qwen3-8B reader comparison

The user requested “try with qwen7B same class” after discussing a larger-reader
control. Official Qwen3 dense sizes include 8B rather than 7B; the 2507 refresh
does not include a 7B/8B checkpoint. Use the official post-trained Qwen/Qwen3-8B,
revision `b968826d9c46dd6066d109eabc6255188de91218`, with thinking explicitly disabled.
This model choice was announced before acquisition/inference. Sources:
[official Qwen3 repository](https://github.com/QwenLM/Qwen3) and
[Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B).

The reference is the existing Qwen3-4B-Instruct-2507 experiment. Model size,
checkpoint training/release and native chat template differ, so results test
reader choice under the same task protocol, not the isolated effect of parameter
count. No claim that this is an 8B-Instruct-2507 checkpoint is permitted.

## Fixed experiment

Copy all 72 cases, references, both system prompts, user messages, archive spans,
questions, condition order and forty cache fixture indices from the completed
paired repair experiment unchanged. There are 24 existing development cases and
48 previously authored fresh cases, each crossed with the original (`baseline`)
and rewritten (`repair`) system prompts: 144 conditions. These are reused frozen
cases for this model comparison, not a newly authored held-out sample.

Only model/tokenizer selection and the required native non-thinking rendering
change. Render with `enable_thinking=False` and append the same ANSWER prefix.
Verify the empty native thinking block is closed before ANSWER and record token
counts/template hashes. Do not inject extra instructions, examples, references
or derived current-state labels. Native input token IDs may differ, but actual
message text must remain identical. Reference answers stay local.

Keep FP32 math attention, TF32 off, seed zero, greedy decoding, fresh prefill,
192 output tokens, 90-word answer limit and 8,192 context-token cap. Greedy decoding
is retained to match the comparison, although the model card recommends sampling
for non-thinking deployment; this does not measure the model's best possible
performance under every decoding setup. No generated reasoning budget is added.

Stage the approximately 16.4 GB checkpoint on a CPU-only worker and verify file
sizes and available upstream SHA-256 hashes before GPU work. Local acquisition
contains tokenizer/configuration/model-card files only. Preserve existing caches
and all previous experimental artifacts. One H100, four CPUs and 32 GiB RAM for
inference, 1,200-second hard/1,150-second internal ceiling, zero automatic retries.
Batch artifact commits every twenty requests and always commit terminal state.

Before answer collection, all forty actual-prompt cache fixtures must pass initial
argmax and sixteen-token-or-EOS cached/fresh trajectory equality, twenty per arm.
Preserve partial artifacts on numerical or runtime failure. Record elapsed time,
observed CPU/GPU billing and terminal app states separately from answer quality.

## Prospective scoring and interpretation

Use the same seven criteria and interpretive rules as the prior paired report:
required value/task correctness, source consistency, whole-answer visible support,
withdrawal compliance, owner attribution, valid body and at most 90 words. UNKNOWN
is distinct from a negative/no preference. A direct user assertion persists absent
a later change; fictional speakers remain distinct from the user. Historical
scope permits original quotes. Correct final values do not excuse unsupported
explanations or restating withdrawn old assignments. A direct current-state
binary denial is permitted when an alternative value is established. Missing
citations are not errors, but explicit wrong source/turn assertions are.

Record unblinded author judgments for all answers with reasons and exact source
and actual-message evidence. This is not independent validation or training-label
admission. Do not alter either prompt or reference after seeing 8B outputs.

The primary reader comparison is 8B versus 4B under the original prompt, which
was the stronger prompt in the completed 4B experiment. Report the rewritten
prompt as a fixed secondary comparison rather than selecting a winner after
seeing 8B outputs. Report strict and required-value counts for each split/arm,
matched corrections/regressions, six case types, and fresh binary/open forms.
Retain the same perfect-suite gates: 24/24 development AND 48/48 fresh, separately
for each arm; primary success requires both under the original prompt. Show
partial improvements even if these gates fail. No population confidence intervals
from four related fresh families or claims of independent question variants.

A better 8B result would support a reader-capability/checkpoint explanation but
cannot isolate capacity from post-training or release differences. A similar or
worse result would not prove that capacity is irrelevant or that either model
cannot learn through targeted training. No training, new prompt search, broader
retrieval run or automatic additional model comparison is included.
