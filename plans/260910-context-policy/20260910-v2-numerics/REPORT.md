# ContextPolicy v2 numerical diagnostic

**Result: FP32 math SDPA passed the exact cache gate on all 40 probes.**

The saved adapter and original model weights were held fixed. No corpus training or external scoring occurred.

| Execution | Exact matches | Maximum same-prefix logit delta | Mode time |
|---|---:|---:|---:|
| bf16_auto | 39/40 | 1.25 | 68.85s |
| bf16_math | 38/40 | 1.90625 | 93.61s |
| fp32_math | 40/40 | 0.00036430359 | 126.18s |

All three modes were declared before this diagnostic; the selection rule was the first mode passing every exact comparison. Every future reader arm must use the selected `fp32_math`, with TF32 disabled and a new runtime identity. Adapter optimization and shared query-blind data/notes generation can retain BF16. The original BF16 failure is preserved.

## Original divergent prefix

| Mode | Cached top token / logit | Fresh top token / logit | Maximum logit delta |
|---|---|---|---:|
| bf16_auto | ` discussion` / 37.75000000 | ` provided` / 37.50000000 | 0.625 |
| bf16_math | ` provided` / 37.50000000 | ` discussion` / 37.50000000 | 0.3125 |
| fp32_math | ` discussion` / 37.47134399 | ` discussion` / 37.47137070 | 8.392334e-05 |

The probes use identical token prefixes, including the original first nine generated tokens. Higher precision substantially reduces the cache-versus-full discrepancy and restores agreement here. This implicates finite-precision execution; it does not isolate a single operation or prove exact behavior on arbitrary prompts.

PyTorch documents that fused attention backends can produce different floating-point outputs, and that the math backend uses float intermediates for BF16 inputs. See [PyTorch 2.7 SDPA](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.scaled_dot_product_attention.html). Backend choice alone was insufficient in this run.

## Verification and cost

- All 11 remote artifact hashes and nine source-snapshot hashes verified.
- Original adapter SHA-256: `aefc1190e9303609cde96bad87b3f3562486af8c31fe313577f62724208cb293`.
- Modal function elapsed: 310.46 seconds; reported app cost: $0.39312410.
- [Modal app](https://modal.com/apps/syntracts/main/ap-uJHzgfAHS0bDDfmDyUgHgP).
- Function call: `fc-01M23SC8GWJ5TQQSFKNM0V5NYR`.
- Source binding: `1498023999b377cecc7de8aa72383b51e973c70804a496e164fe91720e200c23`.
- EOS handling stops each compared branch independently.

This is a development preflight, not a learned-policy result. The 16-token probe horizon does not certify unrestricted long generation. Future latency comparisons must include the FP32 execution cost for all reader arms.
