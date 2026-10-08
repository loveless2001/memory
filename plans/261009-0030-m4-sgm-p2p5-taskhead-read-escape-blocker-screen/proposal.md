# P2.5 taskhead read-escape blocker screen (Stage A), proposal v0.1 (EXPLORATORY)

User "Ok" (#gravity 21971) to claude's offer (21970). This proposal needs codex review. Execution also needs the user's choice of venue (below), and a cap if that venue is paid.

## Why
Diagnosis fa0e44d established, descriptively: taskhead reads overlapped the writes at the reconstructed init, and **by update 100** they had separated from the writes by about 10 cells (≥.97 of read weight on absent cells). The separation persists at 1500. Whether H1 (escaping noisy reads) or H2 (step size with similar q vectors) drives it is untested.

## Question (Stage A)
Does an intervention keep taskhead reads on the memory through the first 100 updates, where the unchanged recipe loses them?

This is a **necessary, not sufficient** condition for learning. The working toy (P2C) also stays near ln 64 and at chance dev accuracy throughout phase 1 (filler 0, updates <1000); it learns only in phase 2. Loss and accuracy are therefore **not** pass criteria here.

## Arms
All arms use the probe recipe: frozen Qwen3-0.6B-Base, learned addresses, taskhead readout, N32, curriculum (phase 1 throughout), seed 0, 100 updates.

| arm | change | tests |
|---|---|---|
| A0 baseline | none | must reproduce the escape in this execution setting, or Stage A is uninformative |
| A1 low lr | lr 3e-3 → 3e-4, all trainable parameters (existing `lr` field) | step size (H2-type) |
| A2 aux address | `aux_address_lambda` 0.1 (existing P2D knob; AddressMLP-only, detached q/k) | whether held reads let content alignment begin. Supervised by binding positions, so it is a diagnostic, not a deployable fix |

A0–A2 use only existing knobs, so memsub is unchanged. Feature centering/whitening (another H2 lever) needs new code and is deferred to a later round. If codex prefers, it can replace A1.

## Readouts (pre-specified, descriptive)
- **Dev evals.** Updates 0/25/50/75/100, on the same dev population as the diagnosis: heldout split, seed 4242, filler 40.
- **Primary:** query absent-read weight at update 100.
  - **escaped:** ≥ 0.9
  - **kept:** ≤ 0.2 (reference points: init ≈ .05; the toy stays at .03–.11 through update 500)
  - **partial:** between the two
- **Geometry.** The cleared diagnosis script runs on each arm's update-100 parameters, giving offsets, alignment, q cosine and cos(q, bound k). This needs a new index entry kind for the Stage-A outputs and a re-review.
- **Descriptive only:** train loss, address-MLP gradient norms (logged every 10 updates), dev accuracy.

## Decision use
- If an arm is **kept** while A0 is **escaped**, propose Stage B: that arm runs the full 1500 updates, 2 seeds. Stage B needs its own proposal, cap and user go.
- If no arm is kept, or A0 does not escape, report that and stop. The write-up option stays open.

## Execution venue: USER CHOICE
1. **Modal, exact recipe (recommended).**
   - L40S or A100, batch 16. Profiled phase-1 cost is about 9.4 s per update, so roughly 20 minutes per arm including evals and load.
   - Estimate about $2–3; proposed cap $4.
   - Ephemeral `modal run` under an outer timeout, using the dev-runner pattern.
2. **Local, free.**
   - RTX 3060 at batch 2. That changes the recipe's batch, so the gradient-noise dynamics differ.
   - About 16–25 s per update, so roughly 3 hours for 3 arms.
   - A local training run crashed the WSL host on 10-06, after which the user moved testing to Modal (21476).

## Not in scope
No 4B, no reserved seeds, no change to registered readings, and no claim beyond the descriptive Stage-A readouts.
