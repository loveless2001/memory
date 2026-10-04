# One supervised 4B reader-repair pilot

The user approved the proposed supervised reader pilot with “go ahead” after
the completed structured-state diagnostic. This newly authorizes training one
answer-only adapter on reviewed new supervision. It does not authorize routing
training, reuse of failed evaluation outputs as labels, a model/hyperparameter
sweep, publication or an automatic follow-up run. Earlier failed reader gates
remain failed; this pilot tests trainability rather than admitting a retrieval
policy or claiming readiness.

## Fixed data and model

Use the same pinned Qwen/Qwen3-4B-Instruct-2507 revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, Torch 2.7.1, Transformers 4.55.2,
PEFT 0.17.0 and safetensors 0.5.3. Keep the original answer-only system prompt,
complete chronological source rendering, supplied ANSWER prefix, greedy decoding,
192-token/90-word answer caps and an 8,192-token context cap for evaluation.
Neither arm gets oracle state or extracted-state annotations.

Training contains 384 separately authored examples: sixteen property/value
families crossed with twelve case types and binary/open questions. Types cover
retained positive values, withdrawal to unknown, later different/same values,
other-owned assertions, quotations after withdrawal, other then personal
assertion, unrelated withdrawal, assistant echoes, explicit negative preference,
explicit no-preference and historical recall. Four statement wording templates
are distributed across the training combinations. Full source turns and short
supported target answers are retained for review. These are synthetic family
variants, not 384 independent situations.

Evaluation retains all 96 previous state-diagnostic cases as regression cases,
without changing their histories, questions or references. None is used for
training. The new primary test has 48 questions on twenty-four separately authored
source families, using property domains absent from training and independently
written source/question phrasing. The test includes multi-step composition,
anaphoric retention and assistant conflicts. Two questions on one history are
related. Exact history/query and family/property disjointness are audited, but
such checks do not prove semantic independence or real-world generalization.
All examples remain author-written synthetic material.

Review targets against full source histories before freezing. Record the author
review explicitly; do not call it independent validation. Preflight must verify
all evidence-turn bounds, target scope and the specific unknown/negative/none
distinction, plus the masking and split tests. Freeze all data, source, ordering,
configuration, this decision rule and the reference review before any GPU work.

## One fixed training recipe

Use LoRA rank 16, alpha 32, dropout 0.05, q_proj and v_proj in all decoder layers,
without bias, embedding or LM-head training. Seed zero. Train exactly two epochs,
with microbatch one and accumulation sixteen: 768 example exposures and 48
optimizer steps. Frozen shuffled example-ID orders are generated before launch.
AdamW uses peak learning rate 1e-4, weight decay 0.01 and gradient clipping 1.0.
The fixed schedule warms up for three steps then decays linearly to zero at the
last optimizer step. The final zero-rate step still processes its batch and
updates optimizer bookkeeping; there are 47 steps with nonzero learning rate.
There is no validation-driven checkpoint selection or test-based adjustment.

Training uses BF16 frozen base parameters and FP32 adapter parameters, with
gradient checkpointing (non-reentrant) and use_cache=False. Preserve original
floating buffers, including rotary frequencies, rather than rounding them via
a blanket BF16 cast. Loss is per-example mean cross-entropy over the reviewed
answer and EOS only. The system, source, question and supplied ANSWER prefix are
not targets. Selected next-token logits avoid materializing unused vocabulary
logits. Do not silently truncate or repair any target. No action/routing loss is
trained, so this does not test whether the model can generate a correct action
prefix or decide to retrieve.

Compute full hashes of all base parameters and buffers before adaptation and
after training. Require exact equality after canonical FP32 conversion. Check
finite, nonzero adapter gradients and absence of frozen-parameter gradients at
every update. Record trainable names/counts, losses, learning rates, actual
example order, token exposure and initial/final adapter hashes. Save the final
adapter, unload it, reload from that saved artifact, and require exact tensor
equality and unchanged base/buffer hashes before adapted evaluation.

## Paired evaluation and decision

Collect the base answers first, then train the fixed adapter, then collect the
adapted answers on identical messages. No semantic test review, test feedback,
early stopping or selection is allowed to influence training. All calls use
fresh prefill and FP32 math attention with TF32 disabled. Twenty frozen actual
evaluation prompts (ten regression, ten new) must pass cached/fresh initial
argmax and up to sixteen-token trajectory equality under each reader, forty
fixtures total. A numerical mismatch stops that phase. The prior 96 baseline
message/output sequences must be checked for exact reproduction.

Use the same seven answer criteria as the preceding diagnostic: required-answer
correctness, source consistency, whole-answer visible support, withdrawal
compliance, ownership, body validity and 90 words. Distinguish unknown from a
negative and explicit no-preference. Historical scope may quote old values;
current explanations must not restate withdrawn assignments. Correct answers
with wrong explanations get separate task/strict scores. Preserve previously
documented judgment nuances and the N01 wording sensitivity in the regression
set; new test questions avoid that accuracy-of-assertion formulation.

The prospective trainability success rule requires ALL of:

- At least six additional strict passes on the 48-question held-out test.
- No regression from strict pass to fail on the 96 regression questions.
- No loss of a base-correct required answer on current known-state controls in
  either split (reference modes known/positive/negative, excluding historical
  scope). This includes positive, negative and explicit no-preference controls.

Report every correction and regression, strict and required-answer scores by
split/type/form, generation tokens and time, and all failures even if the primary
rule passes. Also report clean-suite 96/96 and 48/48 strict gates separately.
The six-answer gain is a predeclared pilot threshold, not a significance test;
no population inference from repeated synthetic templates is claimed. Report
unblinded author judgments with exact source/actual-message evidence. A failed
rule does not trigger another checkpoint, epoch, prompt or model search.

## Bounded execution and artifacts

One H100, four CPUs and 32 GiB RAM, hard timeout 2,400 seconds and internal
deadline 2,300 seconds; zero automatic retries. Reuse the existing pinned model
cache. Batch remote artifact commits every twenty requests, and always save
terminal status. Preserve partial captures and training logs on failure.

Mount only allowlisted runtime modules, training inputs/targets, evaluation
messages, fixed training order, gate IDs and configuration. Evaluation references,
authoring code, prior model outputs and semantic review code stay local.
Training answers are intentionally present only as supervised targets. Preserve
the exact runtime inputs, source snapshots, adapter/config files, optimizer-step
log, parameter/buffer hashes, reload proof, numerical checks and generated tokens.

Download and hash-verify final artifacts, confirm stopped app/zero tasks, read
observed billing and audit training/evaluation token totals. Freeze the final
review/report/manifest only after verification. User-facing results must separate
the trained pilot from broader retrieval, long-history generalization and
independent validation, none of which is established by this experiment.
