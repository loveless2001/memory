# r3 readout — B2 CPU task-gradient-path + retrieval-geometry diagnosis

DIAGNOSTIC ONLY (reduced CPU run: train split, data seed 777, N 32, filler 40, B=1 x K=16 = 16 episodes / 64 queries).
Not a B2 endpoint evaluation. Forward/backward only, no optimizer step. $0, local CPU.
Source 74fd599 (script sha256 0a3d6e96…). Cap 4400 MiB RAM + 1200 MiB swap per condition; maxrss 4.54/4.54/4.55 GB.

## Completion gate (fixed before results, msg 22334)
init exit 0, final exit 0, oracle exit 0 (exits.txt); init/final/oracle.json parse, 16 finite loss entries each → **COMPLETE**.
final weights sha256 2149c975… (matches B2 trained_parameters).

## Losses (mean over 16 episodes; chance CE ln64 = 4.159, top-1 1/64)
| cond | task CE | acc | anchor |
|---|---|---|---|
| init | 4.237 | 0/64 | 0.010 |
| final | 4.154 | 2/64 | 0.547 |
| oracle (init, perfect read=write cells, fill/anchor off) | 4.148 | 0/64 | — |

## Q1: does task CE reach the memory? (None = no graph path)
- init: task-CE gradient reaches q/k/value/beta/address at L6/13/20/27 + head. Only L27 out_proj/alpha are None, as designed: the taskhead reads raw reads (codex 22301).
- oracle: same, plus address_mlp None at every layer. This is expected because oracle addresses bypass the MLP.
- **No structural dead path on the direct task→read→write route.**
- Norms grow with depth at init (value L6 .28 → L13 1.06 → L20 3.5 → L27 7.1; head 8.9).

## Q2: why was the B2-end gradient near zero? The memory had switched off
At final vs init, these are the task-CE gradient norms:
- L13/20/27 q/k/value/beta drop to 1e-5…3e-3, 3–6 orders of magnitude below init.
- head 0.49 vs 8.9.
- L6 keeps large k_proj (4.3) and address_mlp (7.0) task gradients, but value is only .049 and beta .056.

The geometry at final shows why:
- **Write gate collapsed** at L6/L13: beta value-token .0005 / .006 (init .55 / .45). L20/L27 sit at ~.23/.25 with value = filler, i.e. non-selective.
- **Read magnitudes collapsed**: read_norm L6 .026, L13 7e-5, L20 6e-4, L27 8.5e-6 (init .26 / .95 / 2.65 / 6.4).
- **Keys and values collapsed**: pairwise cos across the 32 value tokens is k .95–.98 and v .89–.92 (init k .51–.71, v .53–.72). The stored bindings are nearly indistinguishable.
- **Routing at chance**: q·k top-1 .02–.035 (chance 1/32 = .031). Bound-write address distance ≈ median distance to the other writes, rank ~15–16 of 31.
- L6 address scale blew up: read–write distance ~1000 (init ~2). At L6 the anchor gradient (q_proj 8.6, address_mlp 10.6) exceeds the task gradient. The anchor term is 0.55, 50× its init value.
- My out_proj/alpha "near-zero" lead (22273) is therefore a downstream symptom of this collapse, not a cause. Already withdrawn in 22302.

## Init / oracle geometry (before any training)
- Keys are already similar at init (k pair cos .51–.71: Qwen anisotropy), and q·k bound vs other is at chance at all layers.
- With oracle routing, the read sits slightly nearer the bound value at L13 (rank 12.4 vs ~15.5 chance; cos .20 vs .15) and L27 (14.4; .07 vs .02). It is not nearer at L6/L20 (17.2, 18.4). Descriptive only: heads/queries are not independent.

## Consistency statistic (descriptive)
At B=1 this is cross-episode consistency ‖mean g‖/mean‖g‖ over 16 single-episode gradients. Heuristic noise level 1/√16 = .25.
- init task: .21–.46. oracle task: .22–.63 (alpha highest). final task: .04–.63.
- Labels are episode-specific in this binding task, so low cross-episode consistency is expected even for a real signal. Not a pass/fail measure.

## Interpretation (lead, not tested)
- The task signal does reach the memory at init.
- Over B2 training the sidecar moved to a *silent* state instead of a retrieving one: writes off at L6/L13, keys/values merged, reads ~0. CE then sits at ln64, the loss of ignoring memory.
- Plausible driver: noisy reads from anisotropic, near-collinear Qwen keys raise CE, and shrinking them is the cheapest descent direction.
- This run does not establish when the collapse happened (a step-750 checkpoint may survive in the start-1 archive; unverified) or whether key normalisation / anti-collapse terms would prevent it.

## Unresolved questions
- When during B2 did beta/key collapse occur (a retained step-750 checkpoint, if any, would show it)?
- Would centred/normalised keys or a collapse penalty keep writes selective? Untested; needs a new go.
