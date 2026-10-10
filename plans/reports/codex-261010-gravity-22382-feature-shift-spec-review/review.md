# Review of the feature-shift lead against the spec and retained evidence

For #gravity 22381–22384. **The key-feature lead merits a bounded diagnostic proposal. It is not an established explanation of the Qwen failures.** This is a source/artifact review only: no model load, backbone forward, probe fit, optimizer step, numerical experiment or cloud dispatch was performed. The closed campaign and Q1 cleanup remain unchanged.

## What the evidence supports

The trained Qwen oracle controls show that the memory/readout interface can support high accuracy under their imposed policy. That policy also routes non-binding writes to a separated junk region (`synthetic_binding_task.py`), so it changes write isolation as well as binding addresses. It does not identify learned addressing as the sole cause of the non-oracle failures. Claude accepted this qualification in 22384.

The CPU probe's `top1_qk` measures the rank of the bound value-token write key under a query's content dot product. `rank_addr` is a separate spatial-distance statistic. Both are descriptive initial/end-point measurements. Chance-like content ranking at random initialization does not show that the hidden features lack key information, and initial spatial rank does not establish eventual learnability. Query and key projections are separate random matrices.

The toy no-shift control exists. The primary `p2-load-sweep-v2/summary.md` reports N16 learned accuracy of **6.5% / 6.1%** with shift1, compared with **5.2% / 59.3%** for the shift2 main arm. These are above the 1/64 classification chance level, although the no-shift results fail the useful-routing screen. The main toy's N16 shift comparison was explicitly inconclusive given seed sensitivity. Shift2 was also present in the original N32/N64 toy failures. Thus it was present in toy successes, but it is neither a demonstrated universal requirement nor a sufficient remedy. Backbone, dimensions, initialization, training recipe and readout differ across the toy/Qwen comparisons.

Sources: `M4-SGM.md` registered deviation and P2 results; `plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2/summary.md`; retained CPU terminal audit `plans/reports/codex-261010-gravity-wait49-cpu-probe-terminal-audit/`.

## What feature_shift actually changes

`sgm_model_runtime.py:123` projects **normalized pre-attention** features (`z = layer.input_layernorm(h)`), rather than the selected layer's attention output. Any probe must capture that exact tap. Previous layers can carry preceding-key information into the current value token; this is the information question to measure.

`_shifted` at line144 supplies `[z_current, z_previous]`. `layer_adapter.py:29` expands the input of **q, k, v and beta** together. It does not shift only the write address. In this task a source value follows its key, whereas the query is just the key token and its preceding source token is generally filler. Therefore a full shift also adds a filler-context feature to the query and changes value/gate computation.

Changing input shapes consumes different seeded initialization draws and changes the input scaling. Reusing the seed alone does not preserve AddressMLP/output initialization or the other projection values. A full shift1-versus-shift2 screen tests the entire variant. A mechanistic comparison needs explicit shared parameter blocks and initialization accounting; a zero-previous-block parity control is a useful correctness check, not evidence of improved geometry.

The pinned Qwen defaults and B2 manifest use shift1; tiny defaults use shift2. I found no demonstrated Qwen shift2 result in the reviewed campaign evidence. Treat it as an untested Qwen variant, rather than claiming it is the only difference between successes and failures.

## A useful first diagnostic proposal

Measure whether the exact value-token pre-attention features retain usable information about the preceding key, before choosing a training variant.

- Compare `z_value` with `[z_value, z_previous-key]`. Use the same streamed episodes, selected layers, bounded recent KV and an explicitly fixed SGM-enabled/disabled condition. Capture detached features without retaining backbone graphs. Separate this feature-information probe from final-B2 checkpoint geometry.
- Fit a regularized linear map on a declared training partition to a common target representation, such as the preceding key's pinned input embedding. Evaluate retrieval against the episode's candidate key embeddings, including keys unseen by the probe fit. A key-ID classifier trained on the train key family cannot meaningfully classify unseen held-out key-ID labels without a defined common output representation.
- Include a shuffled-pair null, a current-value-only baseline and a previous-key positive control. Partition by episode, keep probe hyperparameter selection outside the scored partition, and balance/randomize key/value pairing. A strong positive result establishes accessible information; a weak linear result alone does not prove that nonlinear information is absent.
- Retain per-episode metrics and evaluate uncertainty at the episode level. Different heads and queries from one episode are not independent replication. Describe old inspected holdouts as development/diagnostic evidence; reserve an untouched final population before later model selection.
- Record initialization spatial support, correct-versus-other address rank, content alignment, pair separation and write gates as distinct measurements. Do not reject a representation solely because separate untrained q/k projections give chance-like initial ranking.

The numerical proposal needs explicit episode/fit counts, an overall deadline and the existing cgroup RAM/swap bounds. At least a two-batch bounded smoke is needed before a full diagnostic, following the previous OOM/graph-retention lesson. A $0 cloud charge does not remove local resource limits or authorize a new forward. This review supplies no execution authorization and does not reinstate the deleted GPU environment.

## Other candidates and spec fit

| Candidate | Assessment |
|---|---|
| Full feature_shift2 | Reasonable exploratory variant if key information improves. It changes all projection pathways and initialization, so any gain applies to that bundle. Reprofile before deriving a paid cap from B2. |
| Role-separated, shared routing function | More focused exact-binding hypothesis: read address `f(embedding(current query key))`; write address at the value token `f(embedding(preceding source key))`. The same key has the same address input and function. Simply using context-free features with the current distinct q/k maps does **not** guarantee matching addresses. Value content stays associated with the current value token. This exact-match/task-format prior is a separately registered design deviation; non-binding write interference, collisions and content q·k remain distinct issues. |
| Contrastive address supervision | The spec allows a later separately versioned training-pair diagnostic. Negative pairs address the constant-map minimum of a pull-only loss. It remains supervision, requires disjoint probe-fit/evaluation keys/templates and does not by itself establish memory use. Keep address and content negatives distinct. |
| Fixed small, memory-dependent overfit | A useful gate before another N32 screen, adapting the spec's local diagnostic sequence. Reuse keys across several episodes with different value assignments to avoid a fixed key-to-label shortcut; test banks/address perturbations. A fixed-set overfit is not a held-out success. This would require a separate bounded training proposal. |
| Teacher supervision | The spec defines gold-answer NLL plus teacher KL at **aligned registered target positions**, not an already authorized objective over every source token. Denser continuation supervision is a later objective choice; gradient horizon and no-memory shortcuts still matter. |
| Content top-k | A separate design track. A full-bank scan violates bounded neural access. An index must also account for metadata, candidate-generation/update costs and actual accesses; nominal top-k alone does not satisfy the cost claim. |

The most informative next proposal is the **key-information probe with paired feature controls**. If it shows an advantage from the previous-key feature, choose one explicit shift/role-separated variant for a new registered screen. If current value features already expose the key well, that weakens the simple missing-information story and points toward alignment/credit assignment or routing/content coupling. Neither branch establishes the cause without the corresponding intervention.

No automatic progression from a diagnostic to a paid screen, extra seeds, fill/anchor tuning, P3 or 4B scaling follows from this review. The previous campaign's negative results remain intact.

## Primary source pointers

- `M4-SGM.md:47`, `M4-SGM.md:184`, `M4-SGM.md:215`, `M4-SGM.md:222`.
- `memsub/sgm/layer_adapter.py:29`, `memsub/runtime/sgm_model_runtime.py:123`, `memsub/runtime/sgm_model_runtime.py:144`.
- `memsub/sgm/pinned_pretrained_qwen3_backbone.py:27`, `memsub/sgm/synthetic_pilot.py:93`.
- `memsub/sgm/synthetic_binding_task.py:24`, `memsub/sgm/synthetic_pilot_evaluation.py:31`.
- `plans/261005-0210-m4-sgm-p0-p2/m4-sgm-design-spec-v0.1.md:250`, `:361`, `:370`, `:376`, `:378`, `:388`.
