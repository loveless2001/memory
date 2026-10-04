# One revised-supervision reader pilot

The user's new instruction, “cont”, follows the completed first supervised
reader pilot and is interpreted as continuing the reader-repair work with one
focused follow-up. The first result remains frozen and failed its own rule.
This follow-up changes the training mixture, with no model/prompt sweep,
checkpoint search, routing training or production deployment.

## Hypothesis and fixed contrast

The first adapter improved aggregate scores but lost a binary user-assertion
comparison (N09-1) and a known no-preference answer (N12-2). Its original
supervision lacked assistant-conflicting user-assertion comparisons and used
narrow no-preference wording. These are coverage gaps, not established causes.
Keep all 384 original training examples and add 128 new source-authored examples:
64 exact user-supplied-value comparisons across eight factual families, with
and without a conflicting assistant; and 64 preference examples across eight
new families contrasting positive, explicit none, negative and withdrawn states.
No prior evaluation history, question or model answer becomes a training label.

Train a fresh adapter from the same original base, rather than continuing the
previous adapter. Keep the original rank-16 q/v LoRA, alpha 32, dropout .05,
seed zero, AdamW peak 1e-4, weight decay .01, clipping 1, three-step warmup,
linear decay, microbatch one, accumulation sixteen and two epochs. With 512
examples this gives 1,024 exposures and 64 optimizer steps (63 nonzero-LR steps).
The final checkpoint is fixed. This contrasts the complete revised-data recipe;
it does not isolate added supervision from extra updates, changed shuffle or
schedule duration. A compute-matched causal ablation is outside this pilot.

The pinned base, dependencies, answer-only loss, frozen base/buffer hashes,
precision, masking, saved-adapter reload proof and numerical gates follow v1.
Read only the two hash-pinned v1 adapter files for the comparator. Use a dedicated
output volume so old captures/references are not mounted. Neither evaluation
arm gets gold state. Prior answers are captured, fixed training completes, then
reloaded revised answers are captured. Do not inspect new semantic evaluation
outputs until training is complete.

## Data and frozen review

All 144 previously evaluated questions are now regression cases, including the
48-question former test. They are not a fresh test after their results informed
this revision. Preserve their original histories, questions and references.
The new 64-question test uses sixteen new histories/properties with four related
questions each: assistant assertion conflicts, explicit no-preference, negative
preferences, and withdrawal with historical controls. Test sources and questions
are separately written; exact history/query and property overlap are checked.
Synthetic families and related questions do not imply independent samples.

Before launch, author-review the new training constructors and every new test
history/reference. Record the review and all-case evidence, scope, polarity,
masking and disjointness checks. Do not label author review independent. Freeze
this plan, inputs, configuration, source, exact training order and review before
GPU work. Preserve all prior artifacts.

## Prospective decision

Use the same seven strict criteria and separate required-answer correctness.
Retain the original N01 primary judgment and disclose the same wording sensitivity.
All of these are required for this follow-up to pass:

1. Fix both N09-1 and N12-2 to strict passes.
2. Lose none of the v1 adapter's 141 strict passes among the 144 regression cases.
3. Preserve every raw-base-correct required answer from the earlier 144-case
   evaluation; also preserve every v1-correct required answer on the new test.
4. Reach at least 60/64 strict passes on the new test, with a strict score at
   least as high as v1 on those same questions.

Also report the separate perfect-suite 144/144 and 64/64 gates. The 60/64 floor
is a pilot threshold, not a claim of deployment reliability. Report every
correction/regression and all remaining failures, scores by kind/form,
paired-question inconsistencies, generation/token costs and author-review limits.
The N01 sensitivity cannot change the primary decision. A failure does not
trigger another run or recipe change.

## Bound and artifacts

One H100 with four CPUs and 32 GiB RAM; hard timeout 2,400 seconds, internal
2,300-second deadline and no retries. The planned 416 captures compare frozen
v1 with the revised adapter on 208 identical prompts. Twenty fixed actual
prompts per reader must pass initial argmax and up-to-16-token cached/fresh
trajectory checks. Reproduce all 144 prior v1 message/token sequences exactly.

Mount only the allowlisted runtime, five input JSON files, prior checkpoint
weights/config and pinned model cache. The dedicated volume is
`memsub-reader-sft-v2-artifacts`, output prefix `reader-sft-v2/20260911-contrast-v1`.
Always save final status and partial artifacts on an internal failure. Download
and hash-verify outputs, review all new answers, confirm stopped app/zero tasks,
read observed billing and freeze the final report. No automatic follow-up.
