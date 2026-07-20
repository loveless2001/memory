"""FULLRECIPE WP1 — launcher for the instrumented compactor training runs.

Scale points (collapse curve): mid = 1/8 recipe (~1/8 items, 188 steps),
full = 94k-item mixture, 1500 steps (telemetry-based extension to 3000 via
::extend_full — decision logged, not improvised). Existing checkpoint A
(single-t1024-T8k) is the $0 first point.

Adds over the M3.5 launcher: ctx-token packing (no tokenizer at train time),
periodic volume commits while torchrun runs (crash-resumable), watchdog that
reaps the known NCCL-teardown zombie after the DONE marker appears.

Usage:
  modal run modal-runners/modal-fullrecipe-instrumented-compactor-training.py::pack
  modal run --detach modal-runners/modal-fullrecipe-instrumented-compactor-training.py::train_mid
  modal run --detach modal-runners/modal-fullrecipe-instrumented-compactor-training.py::train_full
  modal run --detach modal-runners/modal-fullrecipe-instrumented-compactor-training.py::extend_full
"""

import json

import modal

PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3", "hf_transfer"]
app = modal.App("memsub-fullrecipe-train")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED)
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_file("pyproject.toml", "/root/repo/pyproject.toml")
    .add_local_file(
        "modal-runners/fullrecipe-instrumented-ddp-training-inner-script.py",
        "/root/repo/fullrecipe-instrumented-ddp-training-inner-script.py")
    .add_local_file(
        "modal-runners/fullrecipe-entropy-telemetry-capture-module.py",
        "/root/repo/fullrecipe-entropy-telemetry-capture-module.py")
    .add_local_dir("memsub", "/root/repo/memsub")
)
hf_cache = modal.Volume.from_name("memsub-hf-cache", create_if_missing=True)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": hf_cache, "/artifacts": artifacts}
DOMAINS = ("financial", "legal", "code", "literature")
CTX_TOKENS = 8192
BASE = "/artifacts/corpus-fullrecipe"


@app.function(image=image, volumes=VOLUMES, timeout=7200, memory=32768, cpu=8)
def pack_shard(shard_idx: int, n_shards: int) -> str:
    """Tokenize this shard's docs once, extract each row's ctx window."""
    import numpy as np
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Instruct-2507")
    with open(f"{BASE}/triplets-full.json") as f:
        rows = json.load(f)
    by_doc: dict[str, list[int]] = {}
    for idx, r in enumerate(rows):
        by_doc.setdefault(r["doc_id"], []).append(idx)
    docs = sorted(by_doc)
    my_docs = [d for n, d in enumerate(docs) if n % n_shards == shard_idx]
    my_set = set(my_docs)
    texts = {}
    for domain in DOMAINS:
        if not any(d.startswith(domain + "/") for d in my_set):
            continue
        with open(f"/artifacts/corpus/{domain}.jsonl") as f:
            for line in f:
                rec = json.loads(line)
                if rec["doc_id"] in my_set:
                    texts[rec["doc_id"]] = rec["text"]
    out = {}
    for d in my_docs:
        ids = tok.encode(texts[d], add_special_tokens=False)
        for idx in by_doc[d]:
            r = rows[idx]
            ctx = ids[r["ctx_start"]:r["ctx_start"] + CTX_TOKENS]
            assert len(ctx) == CTX_TOKENS, f"short ctx row {idx}"
            out[str(idx)] = np.asarray(ctx, dtype=np.uint32)
    path = f"{BASE}/ctx-pack-shard-{shard_idx:02d}.npz"
    np.savez_compressed(path, **out)
    artifacts.commit()
    return f"shard {shard_idx}: {len(out)} rows / {len(my_docs)} docs"


@app.function(image=image, volumes=VOLUMES, timeout=7200, memory=65536, cpu=8)
def consolidate(n_shards: int) -> dict:
    import os
    import numpy as np
    with open(f"{BASE}/triplets-full.json") as f:
        full_rows = json.load(f)
    with open(f"{BASE}/triplets-mid.json") as f:
        mid_rows = json.load(f)
    n = len(full_rows)
    arr = np.zeros((n, CTX_TOKENS), dtype=np.uint32)
    filled = np.zeros(n, dtype=bool)
    for s in range(n_shards):
        z = np.load(f"{BASE}/ctx-pack-shard-{s:02d}.npz")
        for k in z.files:
            arr[int(k)] = z[k]
            filled[int(k)] = True
    assert filled.all(), f"unfilled rows: {int((~filled).sum())}"
    np.save(f"{BASE}/ctx-tokens-full.npy", arr)
    idx_of = {r["item_id"]: i for i, r in enumerate(full_rows)}
    mid_idx = [idx_of[r["item_id"]] for r in mid_rows]
    np.save(f"{BASE}/ctx-tokens-mid.npy", arr[mid_idx])
    for s in range(n_shards):
        os.remove(f"{BASE}/ctx-pack-shard-{s:02d}.npz")
    artifacts.commit()
    return {"full_rows": n, "mid_rows": len(mid_rows)}


def _train(tag: str, triplets: str, ctx_npy: str, steps: int,
           save_every: int, seed: int = 1234, lever: str = "none",
           telemetry_every: int = 50,
           tripwire_loss: float = 0.4) -> dict:
    import os
    import subprocess
    import time
    out_dir = f"/artifacts/compactor-checkpoints/{tag}"
    with open(f"{BASE}/train-mixture-stats.json") as f:
        train_stats = json.load(f)
    if not train_stats.get("mixture_sha256") or not train_stats.get(
            "holdout_sha256"):
        raise ValueError("training stats missing manifest/holdout provenance")
    overlap = train_stats.get("overlap_audit", {})
    if overlap.get("document_overlap") != [] or overlap.get(
            "item_overlap") != []:
        raise ValueError("training triplets have not passed the overlap audit")
    os.makedirs(out_dir, exist_ok=True)
    for stale in ("DONE", "TRIPWIRE"):     # would trip the watchdog on resume
        if os.path.exists(f"{out_dir}/{stale}"):
            os.remove(f"{out_dir}/{stale}")
    cmd = ["torchrun", "--standalone", "--nproc_per_node=8",
           "/root/repo/fullrecipe-instrumented-ddp-training-inner-script.py",
           "--triplets-file", triplets, "--ctx-npy", ctx_npy,
           "--probe-ctx-npy", f"{BASE}/ctx-tokens-full.npy",
           "--t-latents", "1024", "--steps", str(steps),
           "--lr", "4e-5", "--out-dir", out_dir,
           "--save-every", str(save_every), "--seed", str(seed),
           "--telemetry-every", str(telemetry_every), "--lever", lever,
           "--tripwire-loss", str(tripwire_loss),
           "--training-manifest-sha256", train_stats["mixture_sha256"],
           "--certification-holdout-sha256", train_stats["holdout_sha256"]]
    proc = subprocess.Popen(cmd)
    # watchdog: commit progress every 2 min; reap NCCL zombie after DONE
    done_marker, waited_after_done = f"{out_dir}/DONE", 0
    while proc.poll() is None:
        time.sleep(120)
        try:
            artifacts.commit()
        except Exception as e:
            print("commit failed:", e, flush=True)
        if os.path.exists(done_marker):
            waited_after_done += 120
            if waited_after_done >= 240:
                print("DONE present but torchrun alive — reaping zombie",
                      flush=True)
                proc.kill()
                break
    proc.wait()
    artifacts.commit()
    tripped = os.path.exists(f"{out_dir}/TRIPWIRE")
    curve = []
    try:
        with open(f"{out_dir}/loss-curve.json") as f:
            curve = json.load(f)
    except FileNotFoundError:
        pass
    return {"tag": tag, "exit": proc.returncode, "gt26_tripwire": tripped,
            "steps_done": len(curve),
            "final_loss": curve[-1] if curve else None,
            "loss_at_300": curve[299] if len(curve) >= 300 else None}


@app.function(image=image, gpu="H100:8", volumes=VOLUMES, timeout=43200,
              memory=262144, cpu=32)
def train(tag: str, triplets: str, ctx_npy: str, steps: int,
          save_every: int, seed: int = 1234, lever: str = "none",
          telemetry_every: int = 50,
          tripwire_loss: float = 0.4) -> dict:
    return _train(tag, triplets, ctx_npy, steps, save_every, seed, lever,
                  telemetry_every, tripwire_loss)


@app.local_entrypoint()
def pack(n_shards: int = 16):
    calls = [pack_shard.spawn(i, n_shards) for i in range(n_shards)]
    for c in calls:
        print(c.get())
    print(json.dumps(consolidate.remote(n_shards)))


@app.local_entrypoint()
def smoke():
    """2-step end-to-end sanity of the instrumented trainer (2 GPUs)."""
    print(json.dumps(smoke_train.remote()))


@app.function(image=image, gpu="H100:2", volumes=VOLUMES, timeout=7200,
              memory=131072, cpu=16)
def smoke_train() -> dict:
    import subprocess
    out_dir = "/artifacts/compactor-checkpoints/fullrecipe-smoke"
    subprocess.run(["rm", "-rf", out_dir])
    with open(f"{BASE}/train-mixture-stats.json") as f:
        train_stats = json.load(f)
    cmd = ["torchrun", "--standalone", "--nproc_per_node=2",
           "/root/repo/fullrecipe-instrumented-ddp-training-inner-script.py",
           "--triplets-file", f"{BASE}/triplets-mid.json",
           "--ctx-npy", f"{BASE}/ctx-tokens-mid.npy",
           "--probe-ctx-npy", f"{BASE}/ctx-tokens-full.npy",
           "--t-latents", "1024", "--steps", "2", "--lr", "4e-5",
           "--out-dir", out_dir, "--save-every", "2",
           "--telemetry-every", "1",
           "--training-manifest-sha256", train_stats["mixture_sha256"],
           "--certification-holdout-sha256", train_stats["holdout_sha256"]]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout[-4000:])
    print(proc.stderr[-4000:])
    artifacts.commit()
    import os
    return {"exit": proc.returncode,
            "done": os.path.exists(f"{out_dir}/DONE"),
            "telemetry": os.path.exists(
                f"{out_dir}/telemetry/entropy-telemetry.jsonl")}


@app.local_entrypoint()
def train_mid():
    h = train.spawn("fullrecipe-mid-t1024-T8k",
                    f"{BASE}/triplets-mid.json",
                    f"{BASE}/ctx-tokens-mid.npy", 188, 47)
    print("spawned mid:", h.object_id)


@app.local_entrypoint()
def train_full():
    h = train.spawn("fullrecipe-full-t1024-T8k",
                    f"{BASE}/triplets-full.json",
                    f"{BASE}/ctx-tokens-full.npy", 1500, 250)
    print("spawned full:", h.object_id)


@app.local_entrypoint()
def extend_full():
    """Entropy still rising at 1500 -> resume same out-dir to 3000."""
    h = train.spawn("fullrecipe-full-t1024-T8k",
                    f"{BASE}/triplets-full.json",
                    f"{BASE}/ctx-tokens-full.npy", 3000, 250)
    print("spawned extension:", h.object_id)


ESCAPE_LEVERS = {"e1": "e1_sqrt_scale", "e2": "e2_learned_temp",
                 "e3": "e3_anchor_noise", "e4": "e4_content_seed"}


@app.local_entrypoint()
def escape_arms(arms: str = "e1,e2,e3,e4", seed: int = 1234):
    """ESCAPE.md E1-E4: mid-scale, one lever each, I1 every 25 steps."""
    handles = []
    for a in arms.split(","):
        tag = f"escape-{a}-mid-t1024-T8k" + ("" if seed == 1234
                                             else f"-seed{seed}")
        handles.append(train.spawn(
            tag, f"{BASE}/triplets-mid.json", f"{BASE}/ctx-tokens-mid.npy",
            188, 47, seed, ESCAPE_LEVERS[a], 25))
    print("spawned:", [h.object_id for h in handles])


@app.local_entrypoint()
def e1full(steps: int = 1500):
    """E1FULL WP1: escaped config (scale sqrt(d_l)), full mixture, GT27
    tripwire 0.45; rerun with --steps 3000 to extend (auto-resume)."""
    h = train.spawn("e1full-t1024-T8k", f"{BASE}/triplets-full.json",
                    f"{BASE}/ctx-tokens-full.npy", steps, 250, 1234,
                    "e1_sqrt_scale", 50, 0.45)
    print("spawned e1full:", h.object_id)


@app.local_entrypoint()
def e1full_clean(steps: int = 1500):
    """Leakage-free E1FULL run bound to the clean-v1 holdout manifest."""
    h = train.spawn("e1full-clean-v1-t1024-T8k",
                    f"{BASE}/triplets-full.json",
                    f"{BASE}/ctx-tokens-full.npy", steps, 250, 1234,
                    "e1_sqrt_scale", 50, 0.45)
    print("spawned clean e1full:", h.object_id)
