# r3 readout r2 — B2 CPU task-gradient-path + retrieval-geometry diagnosis

Supersedes r3-readout.md (posted 22348; kept unchanged). r2 applies codex 22350 corrections (C1–C5 below).

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

## Q2: what the B2 endpoint looks like (endpoint state only; causation not established, C1)
At final vs init, these are the task-CE gradient norms:
- L13/20/27 q/k/value/beta drop to 1e-5…3e-3, 3–6 orders of magnitude below init.
- head 0.49 vs 8.9.
- L6 keeps large k_proj (4.3) and address_mlp (7.0) task gradients, but value is only .049 and beta .056.

The geometry at final shows (projected value-token k/v/beta at write time, NOT full stored bank contents, C2):
- **Write gate collapsed** at L6/L13: beta value-token .0005 / .006 (init .55 / .45). L20/L27 sit at ~.23/.25 with value = filler, i.e. non-selective.
- **Read magnitudes collapsed**: read_norm L6 .026, L13 7e-5, L20 6e-4, L27 8.5e-6 (init .26 / .95 / 2.65 / 6.4).
- **Keys and values collapsed**: pairwise cos across the 32 value tokens is k .95–.98 and v .89–.92 (init k .51–.71, v .53–.72). The stored bindings are nearly indistinguishable.
- **Address routing at chance**: the bound write's address distance ≈ the median distance to the other writes, mean rank ~15–16 of 31 (`rank_addr`/`dist_*`). Separately, the q·k dot-product ranking against value-token keys is also at chance (`top1_qk` .02–.035 vs 1/32). That is not address top-1 (C3).
- L6 address scale blew up: read–write distance ~1000 (init ~2). The anchor numbers in the JSON are UNSCALED; training uses 0.1×anchor (C4). Weighted at L6: q_proj anchor .864 vs task .414 (anchor larger), address_mlp anchor 1.057 vs task 6.98 (task larger). Weighted anchor loss .0547 vs task CE 4.154 at final (init .0010). Anchor dominance is specific to L6 q_proj; it does not hold for the full loss.
- The near-zero task gradients co-occur with this suppressed state. Endpoint measurements cannot say which came first, or whether weak reads drove the collapse (C1). My out_proj/alpha lead (22273) was withdrawn in 22302.

## Init / oracle geometry (before any training)
- q/k are already L2-normalised in layer_adapter.py (C5), so these are cosines of unit vectors. Keys are already similar at init (k pair cos .51–.71), and the q·k dot-product ranking is at chance at all layers.
- With oracle routing, the read sits slightly nearer the bound value at L13 (rank 12.4 vs ~15.5 chance; cos .20 vs .15) and L27 (14.4; .07 vs .02). It is not nearer at L6/L20 (17.2, 18.4). Descriptive only: heads/queries are not independent.

## Consistency statistic (descriptive)
At B=1 this is cross-episode consistency ‖mean g‖/mean‖g‖ over 16 single-episode gradients. Heuristic noise level 1/√16 = .25.
- init task: .21–.46. oracle task: .22–.63 (alpha highest). final task: .04–.63.
- Labels are episode-specific in this binding task, so low cross-episode consistency is expected even for a real signal. Not a pass/fail measure.

## Verified vs hypothesis
- VERIFIED: the task signal reaches the memory write/read parameters at init and under oracle. No structural dead path.
- VERIFIED (endpoint): at step 1500, writes are suppressed at L6/L13, projected value-token k/v are near-collinear at all 4 layers, read norms are ~0, and address routing is at chance. Task CE sits at ≈ ln64.
- HYPOTHESIS (untested): noisy reads from near-collinear keys raise CE, so suppressing the memory is the cheapest descent direction. The endpoint data are consistent with this but do not establish it (C1).
- Not established: when suppression happened (a step-750 checkpoint may survive in the start-1 archive; unverified). Also not established: whether centring/whitening the shared key direction, or an explicit anti-collapse/decorrelation term, would prevent it. L2 normalisation already exists, so it is not a candidate (C5).

## Unresolved questions
- When during B2 did beta/key collapse occur (a retained step-750 checkpoint, if any, would show it)?
- Would centring/whitening keys or a collapse penalty keep writes selective? Untested; needs a new go.

## r2 corrections (codex 22350, all verified against source)
- C1: endpoint changes do not establish causation ("symptom not cause" in r1/22348 overstated).
- C2: geometry = projected value-token k/v/beta at write time, not complete bank contents.
- C3: `top1_qk` = q·k dot-product ranking; routing evidence = address rank/distances.
- C4: probe anchor gradients/losses are unscaled (`query_anchor_loss` docstring "Unscaled"; training adds 0.1×anchor, synthetic_pilot.py:216).
- C5: q/k already L2-normalised (layer_adapter.py:66-67); "normalised keys" is not an untested fix.
