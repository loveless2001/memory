"""torchrun target: DDP training of the Still-class compactor against the
frozen Qwen3-4B teacher (COMPACTOR.md §2.2). Teacher weights frozen; DDP
wraps only the ~50M compactor params. Run by modal-m35-compactor-training.py.

args: --t-latents --steps --ctx-tokens --lr --iterative --out-dir
"""

import argparse
import json
import os
import sys

sys.path.insert(0, "/root/repo")

import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

from memsub.compactor import StillAmortizedKVCompactor
from memsub.compactor.compactor_training_objective import forward_kl_on_answer
from memsub.runtime import CompactedPrefixCache

MICRO_BATCH = 1
EFFECTIVE_BATCH = 32
WARMUP = 100
CHUNK = 2048   # iterative-family chunking (depth tied to ctx/CHUNK)


class Lookahead(torch.optim.Optimizer):
    """Minimal Lookahead wrapper (k=5, alpha=0.5) for the iterative family."""

    def __init__(self, inner, k=5, alpha=0.5):
        self.inner, self.k, self.alpha, self._step = inner, k, alpha, 0
        self.param_groups = inner.param_groups
        self.state = {p: {"slow": p.detach().clone()}
                      for g in inner.param_groups for p in g["params"]}
        self.defaults = inner.defaults

    def step(self, closure=None):
        loss = self.inner.step(closure)
        self._step += 1
        if self._step % self.k == 0:
            for g in self.inner.param_groups:
                for p in g["params"]:
                    slow = self.state[p]["slow"]
                    slow += self.alpha * (p.detach() - slow)
                    p.data.copy_(slow)
        return loss

    def zero_grad(self, set_to_none=True):
        self.inner.zero_grad(set_to_none=set_to_none)


def load_model(device):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-4B-Instruct-2507", torch_dtype=torch.bfloat16,
        attn_implementation="sdpa").to(device).eval()
    model.requires_grad_(False)
    return model, tok


def student_logits(model, cache: CompactedPrefixCache, token_ids, device):
    """Grad-enabled extend (mirrors HFModelRuntime.forward_extend without
    inference_mode): logical position_ids, physical cache_position."""
    n = len(token_ids)
    input_ids = torch.tensor([token_ids], device=device)
    start = cache.next_logical_position
    position_ids = torch.arange(start, start + n, device=device).unsqueeze(0)
    phys = cache.physical_length
    out = model(input_ids=input_ids,
                attention_mask=torch.ones((1, phys + n), dtype=torch.long,
                                          device=device),
                position_ids=position_ids, past_key_values=cache,
                cache_position=torch.arange(phys, phys + n, device=device),
                use_cache=True)
    return out.logits[0]


def build_student_cache(compactor, full_cache, iterative, ctx_len):
    """Single-pass: compact the whole non-sink prefix. Iterative: recurrence
    over 2k chunks with a one-chunk raw lookahead buffer."""
    if not iterative:
        return compactor.module.compact(full_cache)
    n_chunks = ctx_len // CHUNK
    state = None
    for c in range(n_chunks - 1):          # last chunk stays raw (lookahead)
        lo, hi = c * CHUNK, (c + 1) * CHUNK
        chunk_cache = _slice_cache(full_cache, 0 if c == 0 else lo, hi)
        if state is None:
            state = compactor.module.compact(chunk_cache)
        else:
            state = compactor.module.compact(_concat_caches(state, chunk_cache,
                                                            hi))
    raw_tail = _slice_cache(full_cache, (n_chunks - 1) * CHUNK, ctx_len)
    return _concat_caches(state, raw_tail, ctx_len)


def _slice_cache(cache, lo, hi):
    keys, vals = [], []
    for i in range(cache.num_layers):
        k, v = cache.layer_kv(i)
        keys.append(k[:, :, lo:hi])
        vals.append(v[:, :, lo:hi])
    return CompactedPrefixCache.from_tensors(
        keys, vals, logical_positions=list(range(lo, hi)),
        next_logical_position=hi)


def _concat_caches(a, b, next_pos):
    keys, vals = [], []
    for i in range(a.num_layers):
        ka, va = a.layer_kv(i)
        kb, vb = b.layer_kv(i)
        keys.append(torch.cat([ka, kb], dim=2))
        vals.append(torch.cat([va, vb], dim=2))
    return CompactedPrefixCache.from_tensors(
        keys, vals,
        logical_positions=list(a.logical_positions) + list(b.logical_positions),
        next_logical_position=next_pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t-latents", type=int, required=True)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--ctx-tokens", type=int, default=8192)
    ap.add_argument("--lr", type=float, default=4e-5)
    ap.add_argument("--iterative", action="store_true")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    dist.init_process_group("nccl")
    rank, world = dist.get_rank(), dist.get_world_size()
    device = f"cuda:{rank}"
    torch.cuda.set_device(device)
    torch.manual_seed(1234 + rank)

    model, tok = load_model(device)
    compactor = StillAmortizedKVCompactor(model.config, args.t_latents) \
        .to(device, torch.float32)
    compactor = DDP(compactor, device_ids=[rank])

    decay, nodecay = [], []
    for name, p in compactor.named_parameters():
        (decay if p.ndim >= 2 else nodecay).append(p)
    opt = torch.optim.AdamW(
        [{"params": decay, "weight_decay": 0.01},
         {"params": nodecay, "weight_decay": 0.0}],
        lr=args.lr, betas=(0.9, 0.95))
    if args.iterative:
        opt = Lookahead(opt)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt.inner if args.iterative else opt,
        lambda s: min(1.0, (s + 1) / WARMUP))

    with open("/artifacts/corpus-compactor-train/triplets.json") as f:
        triplets = json.load(f)[rank::world]
    needed = {row["doc_id"] for row in triplets}
    doc_text = {}
    for domain in ("financial", "legal", "code", "literature"):
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in needed:
                    doc_text[rec["doc_id"]] = rec["text"]

    accum = EFFECTIVE_BATCH // (world * MICRO_BATCH)
    curve, data_i, tokenized = [], 0, {}
    for step in range(args.steps):
        opt.zero_grad()
        step_loss = 0.0
        for _ in range(accum):
            row = triplets[data_i % len(triplets)]
            data_i += 1
            if row["doc_id"] not in tokenized:
                tokenized.clear()
                tokenized[row["doc_id"]] = tok.encode(
                    doc_text[row["doc_id"]], add_special_tokens=False)
            ids = tokenized[row["doc_id"]]
            ctx = ids[row["ctx_start"]:row["ctx_start"] + args.ctx_tokens]
            if len(ctx) < args.ctx_tokens:
                continue
            seq = row["prompt_ids"] + row["answer_ids"]
            with torch.no_grad():
                out = model(input_ids=torch.tensor([ctx], device=device),
                            use_cache=True)
                full = CompactedPrefixCache.from_prefill(
                    out.past_key_values, len(ctx))
                t_logits = student_logits(model, full.clone_detached(),
                                          seq, device)
            student_cache = build_student_cache(
                compactor, full, args.iterative, len(ctx))
            s_logits = student_logits(model, student_cache, seq, device)
            n_prompt = len(row["prompt_ids"])
            mask = torch.zeros(len(seq), dtype=torch.bool, device=device)
            mask[n_prompt - 1:len(seq) - 1] = True   # predict answer tokens
            gold = torch.tensor(seq[1:] + [tok.eos_token_id], device=device)
            loss = forward_kl_on_answer(t_logits, s_logits, mask, gold) / accum
            loss.backward()
            step_loss += float(loss) * accum
        torch.nn.utils.clip_grad_norm_(compactor.parameters(), 1.0)
        opt.step()
        sched.step()
        if rank == 0:
            curve.append(step_loss / accum)
            if (step + 1) % 25 == 0:
                print(f"step {step + 1}/{args.steps} loss {curve[-1]:.4f}",
                      flush=True)
            if (step + 1) % 250 == 0 or step + 1 == args.steps:
                os.makedirs(args.out_dir, exist_ok=True)
                compactor.module.save(f"{args.out_dir}/compactor.safetensors")
                with open(f"{args.out_dir}/loss-curve.json", "w") as f:
                    json.dump(curve, f)
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
