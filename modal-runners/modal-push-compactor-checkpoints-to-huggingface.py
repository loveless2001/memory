"""Push trained compactor checkpoints from the memsub-artifacts volume
straight to a (private) HuggingFace repo — no local hop.

INVALIDATED CERTIFICATION (2026-07-21): E1FULL evaluation overlapped
training. The model card keeps all affected checkpoints at depth zero pending
a clean holdout retrain and rerun.

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


CARD = r"""---
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

**INVALIDATED CERTIFICATION (2026-07-21).** The E1FULL n=60 evaluation
overlapped training. Its certification, paired-CI, ranking, and deployment
claims are withdrawn pending a clean holdout retrain and rerun. Existing
checkpoints have `max_certified_depth = 0` and are not serving releases.

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

- **`e1full-t1024-T8k`** — historical unfrozen-routing checkpoint (logit
  scale 16), trained on the full mixture for 3,000 steps. Its former n=60
  certification is invalid because the evaluation documents overlapped its
  training manifest. Do not infer quality, ranking, or deployment eligibility
  from the historical table; `max_certified_depth = 0`.

- **`fullrecipe-full-t1024-T8k`** — same data, canonical logit scale: its
  attention kernel stays bitwise frozen at initialization for the whole
  run (position-kernel collapse). Kept as the control the papers rest on
  — and, per the table above, it is not a strictly worse model: it wins
  the aggregation-accuracy axis.
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
without recurrence training. Certification is reported at 60 documents with
paired CIs — an earlier 12-document pass left both aggregation verdicts
statistically unresolved, so treat any small-n compression certification
(including ours, before this fix) with suspicion. These are research
artifacts, not a serving release.
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


@app.function(image=image, volumes=VOLUMES, timeout=1800, memory=8192,
              secrets=[SECRET])
def push_card_only(repo_id: str) -> dict:
    """Refresh README.md + the per-checkpoint notes without re-uploading
    weights (the card outlives any single certification pass)."""
    import os
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.upload_file(path_or_fileobj=CARD.encode(), path_in_repo="README.md",
                    repo_id=repo_id, repo_type="model",
                    commit_message="model card: n=60 certification, anchor scoping")
    n = 0
    for p in _plan():
        note = (f"# {p['tag']}\n\n"
                f"**Load at attention logit scale: {p['logit_scale']}**\n\n"
                f"Files: {len(p['files'])} "
                f"({round(p['bytes'] / 2**30, 2)} GiB). Optimizer state and "
                f"training-only artifacts are not included.\n")
        api.upload_file(path_or_fileobj=note.encode(),
                        path_in_repo=f"{p['tag']}/CHECKPOINT.md",
                        repo_id=repo_id, repo_type="model",
                        commit_message=f"{p['tag']}: load note")
        n += 1
    return {"repo_id": repo_id, "card": True, "notes_refreshed": n}


@app.local_entrypoint()
def refresh_card(repo_id: str):
    print(json.dumps(push_card_only.remote(repo_id), indent=1))


@app.local_entrypoint()
def upload(repo_id: str, private: bool = True):
    print(json.dumps(push.remote(repo_id, private), indent=1))
