# M4-SGM spec review (claude, #gravity msg 21056)

Spec: `agentchattr/uploads/65aedc2e.md` (M4-SGM v0.1, 2026-10-04). Review only; no code touched.

## Verdict

Sound, unusually disciplined brief. Approve P0–P2 **with amendments**. Three-claim split (storage / recovery / scaling), oracle-address arm, causal interventions, matched-access vs matched-storage panels, "errors despite expansion" metric are all right. Main risk is not engineering: it is that learned 2D routing never develops, and the P2 design as written may be unable to detect that.

## Verified against checkout

- HEAD = `f67ff34` (= inspected commit). Worktree dirty: modified README/.gitignore/changelog + untracked CLAUDE-BROADER-*, CLAUDE-JUDGE, CONTEXT-GATE/POLICY. Must be preserved.
- R3: `hf_model_runtime.py` 5 helpers under `@torch.inference_mode()` ✓. R6: E1FULL NO-SHIP, `max_certified_depth=0` ✓. R7 pins ✓.
- Pinned `Qwen3DecoderLayer.forward` (4.55.2) returns a bare tensor; attn-residual → post_attention_layernorm → MLP. §5.4 insertion = ~10-line explicit wrapper. Feasible.
- Qwen3-4B-Instruct-2507 `max_position_embeddings=262144` → 1K–32K extrapolation needs no RoPE change.
- CONTEXT-POLICY: reader/retrieval campaign PAUSED 2026-09-11. M4 is a new line; user should confirm it is a fresh authorization, not a resumption.

## Findings (ranked)

1. **Collapse is the default attractor; P2 task must be capacity-forcing.** Shared AddressMLP + overlapping init → all writes land near origin. With few bindings, one 3×3 neighborhood (≈9·d_k keys/head) holds everything, so there is no gradient pressure to spread; SGM ≡ single DeltaNet bank and "learned routing" is untestable. Repo precedent: ESCAPE D1 — routing pathway got ~0 gradient while value/output path trained normally. Amend: P2 binding count ≫ 9·d_k per head (tiny d=8 → ≫72); preregister dead-run = effective written cells (participation ratio of write mass) below threshold, or learned ≈ fixed-single-bank within noise.
2. **Token-serial ingestion is infeasible past P2; add chunk-serial + detached-source-feature training.** (a) Chunk size C ≤ local window W keeps the coverage invariant "every past token ∈ exact KV ∪ committed bank": intra-chunk info comes from exact attention, bank read at chunk start, bank writes (still sequential per cell, cheap) at chunk end. Distinct policy identity; test C=1 ≡ token-serial reference. (b) Write-path gradients (W_k, W_v, β, AddressMLP) need only source z_t, not backprop through 36 frozen layers × T tokens. Ingest backbone no_grad, keep z_t, recompute bank writes with grad. Approximation drops ∂z_t/∂θ via earlier-layer reads (second order while α small). Register as explicit mode; validate gradient cosine vs full-gradient on short tiny episodes. Bank itself stays non-detached, consistent with §6.
3. **Screening rule omits the comparator most likely to dominate.** 5pp rule is vs local-only and fixed/random-address. On exact random key/value bindings, plain archive retrieval of raw spans will likely be near-perfect at ~0 neural state. Amend: archive-retrieval-only reported on the screen (mandatory, non-gating) + ≥1 preregistered family where lexical retrieval is predicted to fail (paraphrased/implicit query, many-span aggregation). Otherwise a "storage/read win" can be real and useless.
4. **Writes are temporally dense.** β = sigmoid > 0 always → every source token writes (and allocates) up to 9 cells per bank. "Sparse" is spatial only. With 1024-cell fail-closed cap, 16K/32K points may report allocation failure, not quality. Decide pre-P3: hard/thresholded write gate (straight-through) or accept + report. Preregister both failure modes (collapse #1, overflow here).
5. **P0–P2 scope cut (YAGNI).** Provenance SQLite postings, safetensors manifests, redaction of live SGM state (SGM-10/11, `provenance_index.py`, `snapshot_store.py`) only matter if the mechanism works. Tag SGM-10/11 as P4 like SGM-12/13; keep in-memory fork/snapshot isolation (SGM-09) in P2.
6. **Add P2.5: frozen Qwen3-0.6B real-LM pilot, local, $0.** Random tiny LM + task head proves the mechanism only (spec says so). A real small frozen LM tests the actual interface question (can a frozen pretrained residual stream use injected reads) before any paid 4B run. Separate model identity/labels.

## Minor

- Init: α=sigmoid(−4)≈0.018 × small W_out → read-path grads ∝ product of two small numbers. LoRA-style W_out=0, α=1 gives exact bypass at init and nonzero grads after step 1. Either is fine; record choice.
- One-shot readback gain with β=1 = Σw² (2D) ∈ [0.25, 0.35] (per-cell delta + interpolated read); converges to 1 only on repeated writes. Expect it; log it.
- Storage arithmetic: max bank 64 MiB ≈ **455 tokens** of Qwen3-4B bf16 KV (147,456 B/token). Matched-storage comparator ≈ 1.5K-token window; 32K full KV ≈ 4.5 GiB.
- Novelty framing: within-cell = DeltaNet; router-sharded linear-attn state has neighbors (mixture-of-memories / sparse-state-expansion line). Distinct part = unbounded continuous 2D address + frozen-LM sidecar + exact recovery. Don't oversell.

## Unresolved questions

- Is M4 a fresh authorization given the 2026-09-11 pause? (user)
- Roles: codex executor / claude auditor as in other channels? (user)
- Local GPU torch for 0.6B pilot vs CPU-only pinned env (codex to check; pinned env must not be upgraded).
