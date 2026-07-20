"""Push trained compactor checkpoints from the memsub-artifacts volume
straight to a (private) HuggingFace repo — no local hop.

Uploads inference weights only: `compactor.safetensors` plus the
step-tagged snapshots (the training trajectory the papers plot).
EXCLUDED by default: `resume-state.pt` (1.3 GB optimizer state per run,
useful only for resuming training) and the 2-step `fullrecipe-smoke`
scratch run.

Each checkpoint dir gets a CHECKPOINT.md recording the one thing the
safetensors metadata does NOT carry: the attention logit scale it must be
loaded at. E1-class checkpoints (ESCAPE lever) train and deploy at
d_l = 16; loading them at the canonical 256 silently changes routing.

Usage:
  modal run modal-runners/modal-push-compactor-checkpoints-to-huggingface.py::dry_run
  modal run --detach modal-runners/modal-push-compactor-checkpoints-to-huggingface.py::push \\
      --repo-id <user>/memsub
"""

import json

import modal

app = modal.App("memsub-hf-push")
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface_hub>=0.34,<1", "hf_transfer")
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/artifacts": artifacts}
SECRET = modal.Secret.from_name("huggingface-token")

BASE = "/artifacts/compactor-checkpoints"
SKIP_DIRS = {"fullrecipe-smoke"}          # 2-step harness smoke test
SKIP_FILES = {"resume-state.pt"}          # optimizer state, training-only

# logit scale each checkpoint family must be LOADED at (see module docstring)
E1_LEVER_PREFIXES = ("escape-e1-", "escape-e2-", "e1full-")


def _logit_scale(tag: str) -> str:
    if tag.startswith("escape-e2-"):
        return ("learned per-layer temperature (init 16, clamped [1, 256]); "
                "the trained `attn_temp` values are in the state dict and "
                "must be applied as the attention logit scale")
    if tag.startswith(E1_LEVER_PREFIXES):
        return "16 (= sqrt(d_l)) — NOT the canonical 256"
    return "256 (canonical d_l)"


def _plan() -> list[dict]:
    import os
    out = []
    for tag in sorted(os.listdir(BASE)):
        d = os.path.join(BASE, tag)
        if not os.path.isdir(d) or tag in SKIP_DIRS:
            continue
        files = []
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if not os.path.isfile(p) or name in SKIP_FILES:
                continue
            if not name.endswith((".safetensors", ".json")):
                continue
            files.append({"name": name, "bytes": os.path.getsize(p)})
        if files:
            out.append({"tag": tag, "files": files,
                        "bytes": sum(f["bytes"] for f in files),
                        "logit_scale": _logit_scale(tag)})
    return out


@app.function(image=image, volumes=VOLUMES, timeout=1800, memory=8192)
def dry_run() -> dict:
    plan = _plan()
    total = sum(p["bytes"] for p in plan)
    return {"checkpoint_dirs": len(plan),
            "total_gib": round(total / 2**30, 2),
            "skipped_dirs": sorted(SKIP_DIRS),
            "skipped_files": sorted(SKIP_FILES),
            "detail": [{"tag": p["tag"], "files": len(p["files"]),
                        "gib": round(p["bytes"] / 2**30, 2),
                        "logit_scale": p["logit_scale"]} for p in plan]}


CARD = """---
license: apache-2.0
library_name: pytorch
tags: [kv-cache, compaction, long-context, qwen3]
---

# memsub — trained KV-cache compactors

Per-layer Perceiver compactors ("Still-class") trained against a **frozen**
Qwen3-4B-Instruct-2507 base. Each checkpoint compresses the non-sink KV
prefix of one 36-layer cache into `t` latent slots per KV head.

**Private research artifacts.** The accompanying papers are unpublished
drafts; numbers here are provided so the checkpoints are usable, not as a
citable record.

## Loading (read this first)

The attention **logit scale is not stored in the safetensors metadata** and
must be set correctly at load time, or routing changes silently:

| checkpoint family | logit scale |
|---|---|
| `single-*`, `iterative-*`, `fullrecipe-*` | 256 (canonical `d_l`) |
| `escape-e1-*`, `e1full-*` | **16** (`sqrt(d_l)`) |
| `escape-e2-*` | learned per-layer `attn_temp` from the state dict |
| `escape-e3-*`, `escape-e4-*` | 256 (canonical) |

```python
from memsub.compactor import StillAmortizedKVCompactor
comp = StillAmortizedKVCompactor.load("compactor.safetensors", base_config)
for layer in comp.layers:                     # E1-class checkpoints only
    for m in list(layer.cross) + list(layer.selfattn):
        m.d_l = 16
```

## Checkpoints

- **`e1full-t1024-T8k`** — the headline model: unfrozen routing (logit
  scale 16), full 76k-item mixture, 3,000 steps. Passes a two-axis
  certification against a matched-budget eviction baseline on a
  **task-anchored** predicate (aggregation accuracy +0.042 vs −0.049;
  silent fact loss 0.153 vs 0.597) at recurrence **depth 1**. It does
  **not** pass the distributional (teacher-KL) predicate: 0.1385 vs
  eviction's 0.1218. Certification scope matters — see below.
- **`fullrecipe-full-t1024-T8k`** — same data, canonical logit scale: its
  attention kernel stays bitwise frozen at initialization for the whole
  run (position-kernel collapse). Kept as the control the papers rest on.
- **`escape-e{1,2,3,4}-mid-*`** — 188-step mid-scale lever study
  (e1 = sqrt scale, e2 = learned temperature, e3 = anchor noise,
  e4 = content-seeded init), plus e1 seed replications.
- **`single-*`, `iterative-*`** — the original 1/40-scale lineage. These
  were trained on a harness that did not synchronize gradients across
  workers (effective batch 4, single replica); behavioral measurements of
  them are valid, training-scale attribution is not.

Step-tagged snapshots (`compactor-step-*.safetensors`) are the training
trajectory; `compactor.safetensors` is the final state.

## Scope and limits

One base model, one architecture family; extractive-MCQ certification with
letter-match equivalence, single-turn contexts; depth-4 recurrence collapses
without recurrence training. These are research artifacts, not a serving
release.
"""


@app.function(image=image, volumes=VOLUMES, timeout=14400, memory=16384,
              secrets=[SECRET])
def push(repo_id: str, private: bool = True) -> dict:
    import os
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repo_id, private=private, repo_type="model",
                    exist_ok=True)
    plan = _plan()

    api.upload_file(path_or_fileobj=CARD.encode(), path_in_repo="README.md",
                    repo_id=repo_id, repo_type="model",
                    commit_message="model card")

    pushed = []
    for p in plan:
        tag = p["tag"]
        note = (f"# {tag}\n\n"
                f"**Load at attention logit scale: {p['logit_scale']}**\n\n"
                f"Files: {len(p['files'])} "
                f"({round(p['bytes'] / 2**30, 2)} GiB). Optimizer state and "
                f"training-only artifacts are not included.\n")
        api.upload_file(path_or_fileobj=note.encode(),
                        path_in_repo=f"{tag}/CHECKPOINT.md",
                        repo_id=repo_id, repo_type="model",
                        commit_message=f"{tag}: load note")
        api.upload_folder(
            folder_path=f"{BASE}/{tag}", path_in_repo=tag, repo_id=repo_id,
            repo_type="model",
            allow_patterns=["*.safetensors", "*.json"],
            ignore_patterns=[f"*{s}" for s in SKIP_FILES],
            commit_message=f"{tag}: weights + trajectory")
        pushed.append({"tag": tag, "gib": round(p["bytes"] / 2**30, 2)})
        print(f"pushed {tag} ({pushed[-1]['gib']} GiB)", flush=True)
    return {"repo_id": repo_id, "private": private, "dirs": len(pushed),
            "total_gib": round(sum(x["gib"] for x in pushed), 2),
            "pushed": pushed}


@app.local_entrypoint()
def show():
    print(json.dumps(dry_run.remote(), indent=1))


@app.local_entrypoint()
def upload(repo_id: str, private: bool = True):
    print(json.dumps(push.remote(repo_id, private), indent=1))
