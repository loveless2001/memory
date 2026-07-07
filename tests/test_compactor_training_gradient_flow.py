"""Training-path mechanics on the tiny model: gradients flow from the KL
loss through the student forward and the compactor into the latent banks;
one optimizer step reduces nothing catastrophic (loss finite, params move)."""

import torch

from conftest import corpus_token_ids

from memsub.compactor import StillAmortizedKVCompactor
from memsub.compactor.compactor_training_objective import forward_kl_on_answer
from memsub.runtime import CompactedPrefixCache


def _grad_student_logits(model, cache, token_ids, device="cpu"):
    n = len(token_ids)
    start = cache.next_logical_position
    phys = cache.physical_length
    out = model(input_ids=torch.tensor([token_ids], device=device),
                attention_mask=torch.ones((1, phys + n), dtype=torch.long),
                position_ids=torch.arange(start, start + n).unsqueeze(0),
                past_key_values=cache,
                cache_position=torch.arange(phys, phys + n),
                use_cache=True)
    return out.logits[0]


def test_kl_gradients_reach_latents_and_step_updates(runtime):
    torch.manual_seed(0)
    model = runtime.model
    model.requires_grad_(False)
    ids = corpus_token_ids(runtime.tokenizer, 68)
    seq = runtime.tokenizer.encode(" The answer is B because the text",
                                   add_special_tokens=False)

    with torch.no_grad():
        out = model(input_ids=torch.tensor([ids]), use_cache=True)
        full = CompactedPrefixCache.from_prefill(out.past_key_values, len(ids))
        t_logits = _grad_student_logits(model, full.clone_detached(), seq)

    compactor = StillAmortizedKVCompactor(model.config, t_latents=16).float()
    student_cache = compactor.compact(full)
    assert student_cache.physical_length == 4 + 16
    s_logits = _grad_student_logits(model, student_cache, seq)

    mask = torch.zeros(len(seq), dtype=torch.bool)
    mask[2:-1] = True
    gold = torch.tensor(seq[1:] + [0])
    loss = forward_kl_on_answer(t_logits, s_logits, mask, gold)
    assert torch.isfinite(loss)
    loss.backward()

    grads = [p.grad for p in compactor.parameters() if p.grad is not None]
    assert grads, "no gradients reached the compactor"
    assert compactor.layers[0].latents.grad is not None
    assert any(float(g.abs().sum()) > 0 for g in grads)

    before = compactor.layers[0].latents.detach().clone()
    torch.optim.AdamW(compactor.parameters(), lr=1e-3).step()
    assert not torch.equal(before, compactor.layers[0].latents.detach())
