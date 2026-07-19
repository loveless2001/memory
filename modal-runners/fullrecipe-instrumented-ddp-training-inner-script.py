"""torchrun target: FULLRECIPE WP1 — instrumented DDP training of the Still
compactor. Identical objective/optimizer/schedule to the M3.5 inner script
(corrected KL, post-f214c0f), plus:
  I1  entropy telemetry every --telemetry-every steps on a fixed 128-item
      probe batch (first 128 rows of the triplets file, 16 per rank)
  step-tagged checkpoints + optimizer resume-state every --save-every steps
  GT12-class loss tripwire at --tripwire-step (mean of prior 25 steps < 0.4)
  save-then-exit watchdog: DONE marker + os._exit(0), no NCCL teardown
  FIX vs M3.5 harness: that script bypassed the DDP wrapper (module.compact),
  so gradients were NEVER all-reduced — replicas trained independently at
  batch 4 with per-rank init. Here: identical init on every rank (same seed)
  + explicit grad all-reduce -> true effective batch 32, with a rank-0 param
  broadcast at every save to pin replicas bitwise-identical.

Data path: pre-packed ctx token array (ctx-tokens .npy, row-aligned with the
triplets file) — no tokenizer at train time.

args: --triplets-file --ctx-npy --t-latents --steps --lr --out-dir
      [--telemetry-every 50] [--save-every 250] [--tripwire-step 300]
      [--seed 1234]
"""

import argparse
import importlib.util
import json
import os
import sys

sys.path.insert(0, "/root/repo")

import numpy as np
import torch
import torch.distributed as dist

from memsub.compactor import StillAmortizedKVCompactor
from memsub.compactor.compactor_training_objective import forward_kl_on_answer
from memsub.runtime import CompactedPrefixCache

MICRO_BATCH = 1
EFFECTIVE_BATCH = 32
WARMUP = 100
PROBE_ITEMS = 128
TRIPWIRE_LOSS = 0.4

_spec = importlib.util.spec_from_file_location(
    "entropy_telemetry",
    "/root/repo/fullrecipe-entropy-telemetry-capture-module.py")
telemetry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(telemetry)


def load_model(device):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-4B-Instruct-2507", torch_dtype=torch.bfloat16,
        attn_implementation="sdpa").to(device).eval()
    model.requires_grad_(False)
    return model, tok


def student_logits(model, cache, token_ids, device):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--triplets-file", required=True)
    ap.add_argument("--ctx-npy", required=True)
    ap.add_argument("--t-latents", type=int, default=1024)
    ap.add_argument("--steps", type=int, required=True)
    ap.add_argument("--lr", type=float, default=4e-5)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--probe-ctx-npy", default=None,
                    help="ctx array whose first 128 rows form the fixed I1 "
                         "probe batch (default: --ctx-npy); pass the FULL "
                         "array on every scale point so Q1 curves compare "
                         "like-for-like")
    ap.add_argument("--telemetry-every", type=int, default=50)
    ap.add_argument("--save-every", type=int, default=250)
    ap.add_argument("--tripwire-step", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    dist.init_process_group("nccl")
    rank, world = dist.get_rank(), dist.get_world_size()
    device = f"cuda:{rank}"
    torch.cuda.set_device(device)
    torch.manual_seed(args.seed)          # SAME init on every rank

    model, tok = load_model(device)
    compactor = StillAmortizedKVCompactor(model.config, args.t_latents) \
        .to(device, torch.float32)
    telemetry.install(int(model.config.num_hidden_layers), device)
    telemetry.mark_layers(compactor)

    decay, nodecay = [], []
    for name, p in compactor.named_parameters():
        (decay if p.ndim >= 2 else nodecay).append(p)
    opt = torch.optim.AdamW(
        [{"params": decay, "weight_decay": 0.01},
         {"params": nodecay, "weight_decay": 0.0}],
        lr=args.lr, betas=(0.9, 0.95))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / WARMUP))

    with open(args.triplets_file) as f:
        all_rows = json.load(f)
    ctx_arr = np.load(args.ctx_npy, mmap_mode="r")
    assert len(all_rows) == ctx_arr.shape[0], "ctx array misaligned"
    rows = all_rows[rank::world]
    row_gidx = list(range(rank, len(all_rows), world))
    probe_arr = np.load(args.probe_ctx_npy, mmap_mode="r") \
        if args.probe_ctx_npy else ctx_arr
    probe_gidx = list(range(min(PROBE_ITEMS, probe_arr.shape[0])))[rank::world]
    probe_ctx = [probe_arr[g].tolist() for g in probe_gidx]

    # ---- resume ------------------------------------------------------------
    start_step, curve, data_i = 0, [], 0
    resume_path = f"{args.out_dir}/resume-state.pt"
    if os.path.exists(resume_path):
        st = torch.load(resume_path, map_location=device,
                        weights_only=False)
        compactor.load_state_dict(st["compactor"])
        opt.load_state_dict(st["optimizer"])
        sched.load_state_dict(st["scheduler"])
        start_step, curve, data_i = st["step"], st["curve"], st["data_i"]
        if rank == 0:
            print(f"resumed from step {start_step}", flush=True)

    def save_state(step):
        if rank != 0:
            return
        os.makedirs(args.out_dir, exist_ok=True)
        compactor.save(f"{args.out_dir}/compactor.safetensors")
        compactor.save(
            f"{args.out_dir}/compactor-step-{step:05d}.safetensors")
        torch.save({"compactor": compactor.state_dict(),
                    "optimizer": opt.state_dict(),
                    "scheduler": sched.state_dict(),
                    "step": step, "curve": curve, "data_i": data_i},
                   resume_path + ".tmp")
        os.replace(resume_path + ".tmp", resume_path)
        with open(f"{args.out_dir}/loss-curve.json", "w") as f:
            json.dump(curve, f)

    def probe(step):
        rec = telemetry.probe_pass(
            step, model, compactor, probe_ctx, device,
            f"{args.out_dir}/telemetry", rank, dist,
            save_item_argmax=(step % args.save_every == 0
                              or step in (0, args.steps)))
        if rank == 0 and rec:
            print(f"[tele] step {step} entropy "
                  f"{rec['entropy_mean_over_layers']:.4f} "
                  f"kept-l0 {rec['kept_positions_per_layer'][0]}", flush=True)

    if start_step == 0:
        probe(0)                        # init-state point on the curve

    accum = EFFECTIVE_BATCH // (world * MICRO_BATCH)
    for step in range(start_step, args.steps):
        opt.zero_grad()
        step_loss = 0.0
        for _ in range(accum):
            i = data_i % len(rows)
            row, gidx = rows[i], row_gidx[i]
            data_i += 1
            ctx = ctx_arr[gidx].tolist()
            seq = row["prompt_ids"] + row["answer_ids"]
            with torch.no_grad():
                out = model(input_ids=torch.tensor([ctx], device=device),
                            use_cache=True)
                full = CompactedPrefixCache.from_prefill(
                    out.past_key_values, len(ctx))
                t_logits = student_logits(model, full.clone_detached(),
                                          seq, device)
            student_cache = compactor.compact(full)
            s_logits = student_logits(model, student_cache, seq, device)
            n_prompt = len(row["prompt_ids"])
            mask = torch.zeros(len(seq), dtype=torch.bool, device=device)
            mask[n_prompt - 1:len(seq) - 1] = True
            gold = torch.tensor(seq[1:] + [tok.eos_token_id], device=device)
            loss = forward_kl_on_answer(t_logits, s_logits, mask, gold) / accum
            loss.backward()
            step_loss += float(loss) * accum
        # true effective-batch-32: average grads across ranks (M3.5 fix)
        for p in compactor.parameters():
            if p.grad is not None:
                dist.all_reduce(p.grad)
                p.grad /= world
        torch.nn.utils.clip_grad_norm_(compactor.parameters(), 1.0)
        opt.step()
        sched.step()
        n = step + 1
        loss_t = torch.tensor([step_loss / accum], device=device)
        dist.all_reduce(loss_t)
        if rank == 0:
            curve.append(float(loss_t.item()) / world)
            if n % 25 == 0:
                print(f"step {n}/{args.steps} loss {curve[-1]:.4f}",
                      flush=True)

        # GT12-class tripwire (GT26): all ranks agree via broadcast
        if n == args.tripwire_step and args.tripwire_step > 0:
            flag = torch.zeros(1, device=device)
            if rank == 0:
                recent = float(np.mean(curve[-25:]))
                if recent > TRIPWIRE_LOSS:
                    flag[0] = 1
                    with open(f"{args.out_dir}/TRIPWIRE", "w") as f:
                        json.dump({"step": n, "mean_loss_25": recent}, f)
                    save_state(n)
            dist.broadcast(flag, 0)
            if flag.item():
                dist.barrier()
                os._exit(3)

        if n % args.telemetry_every == 0 or n == args.steps:
            probe(n)
        if n % args.save_every == 0 or n == args.steps:
            save_state(n)
            # pin replicas bitwise-identical at every checkpoint
            for p in compactor.parameters():
                dist.broadcast(p.data, 0)
        dist.barrier()

    if rank == 0:
        with open(f"{args.out_dir}/DONE", "w") as f:
            f.write(str(args.steps))
        print("training complete — exiting without NCCL teardown", flush=True)
    dist.barrier()
    os._exit(0)


if __name__ == "__main__":
    main()
