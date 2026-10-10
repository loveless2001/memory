# Review of the fallback-first proposal, #gravity 22104

**Decision:** fix-first is a reasonable engineering choice if the goal is to find a useful Qwen memory variant rather than identify the original cause. The proposal is not ready for execution as written. Its support metric can pass by construction, and a nearest-cell lookup does not necessarily restore address gradients. No implementation, backbone forward, optimizer step, GPU query, paid call or launch was performed in this review.

## What the fallback can and cannot establish

Selecting an occupied cell can restore a gradient path into its contents and the content query. A hard nearest-cell index is locally constant in the read address, so it does not itself create a gradient telling the address to return to the original written region. A soft weighting or explicit distance/anchor objective would have different derivatives and must be specified. Even differentiable content weighting does not guarantee a useful or restoring gradient for every head/example.

A fixed CPU Torch 2.7.1+cpu example, with one thread and no optimizer, used read address (10,0), occupied coordinates (0,0)/(1,0), values 1.5/−1, q=1, hard nearest selection and binary logits [read,0] with target 0. Selected cell: (1,0). Loss: 1.31326163. Autograd gives:

| Variable | Loss gradient |
|---|---|
| Read address | None: no differentiable path through argmin |
| Content query q | +0.73105860 |
| Stored values | (0, −0.73105860) |

Thus restoring a content-learning path is a legitimate hypothesis; claiming that nearest lookup always supplies an address-restoring signal is not justified. Occupied cells can also contain zero/uninformative reads.

The example is reproducible with CPU tensors: `nearest=((coords-address)**2).sum(-1).argmin(); read=q*values[nearest]`, followed by cross-entropy on `[read,0]` and `autograd.grad(..., allow_unused=True)`. CUDA visibility was disabled and every tensor was on CPU.

## Avoid a pass criterion that the implementation guarantees

If fully absent reads are replaced by occupied-cell reads and the reported absent mass is measured **after** that replacement, a threshold on it can be met even while every learned address remains fully escaped. In fact, replacing all fully absent lookups with fully occupied lookups removes the absence-based indicator of their escape. This would verify support mechanics, not learned retention or retrieval.

Record the original stencil's absent mass before fallback, fallback frequency, the resulting read support, read-feature variation, and appropriate content/gradient diagnostics separately. If the purpose is to restore the original spatial router, apply a preregistered retention threshold to the **original** stencil measure. If the purpose is to train a different effective lookup, persistent fallback may be acceptable; its 100-step check should be described as a mechanical gate. Useful retrieval remains a later held-out task and intervention question.

Specify behavior when a bank is empty, nearest-neighbor count, distance metric, ties, weights, normalization and all-empty trigger, and whether fallback applies during source ingestion, query, or both. Source-ingestion reads affect subsequent writes/backbone features, so these choices change the recurrence. The implementation needs an explicit policy/config identity, default-off baseline parity and CPU checks of the claimed gradients. This is a new addressing variant, not merely an instrumentation change to the frozen A0 experiment.

## Budget arithmetic is plausible as an estimate, not a bound

The existing A0 artifact records 642.07646 seconds for the 100-update child. Its logged optimizer-step times have median 5.03130114 seconds. Current listed resource rates for an L40S, 4 CPU cores and 32 GiB sum to $0.00066544/second. See [Modal pricing](https://modal.com/pricing); the prior run's conservative ledger used a higher CPU margin.

At those base resources, the recorded child duration corresponds to about $0.4273, before additional load/idle/shutdown work and any fallback overhead. Thus roughly $0.5 for a similar short run is plausible, not profiled for the new lookup.

1500 × the filler-0 median logged optimizer-step time corresponds to about $5.022 **for optimizer-step time alone**. It excludes dev evaluations, loading, the longer filler-40 phase, fallback search/graph costs and shutdown. Therefore “worst case about $6” is not an established bound. A concrete future ledger needs a whole-job deadline, maximum starts, cleanup and an explicit spend assumption; billing collection and platform shutdown limits must remain qualified. No new cost cap or execution scope is authorized here.

## Interpretation and next preparation

A successful longer trial would support this particular fallback variant under its registered conditions, with retrieval evidence beyond chance and appropriate memory/address interventions. A negative trial would be a negative result for that variant, seed and recipe. It could justify a practical stop decision, but would not establish that Qwen cannot use memory, or that every SGM fix/design is exhausted.

The next useful preparation is an exact fallback definition and CPU implementation/gradient review, followed by a concrete staged experiment proposal if the user wants to run it. This review does not propose a job, authorize GPU use, or authorize automatic progression from 100 to 1500 updates. The user's existing GPU stop remains in force.
