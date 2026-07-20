"""FULLRECIPE P0/C2 — Still-recipe training mixture manifest.

Domain-downsampled to the smallest B.3 domain (code = 23,563) -> 94,252
nominal items. Per-domain selection: sort by (doc_id, item_id), take the
cap. Marks which items already carry M3.5 rationale traces (C1 audit:
19,619) and emits the remainder work-list for the batched teacher pass.
Manifest sha256 goes into compaction_policy_version material.

Usage:
  modal run modal-runners/modal-fullrecipe-c2-mixture-manifest.py::build_manifest
"""

import hashlib
import json

import modal

app = modal.App("memsub-fullrecipe-c2-manifest")
PINNED = ["torch==2.7.1", "transformers==4.55.2", "safetensors==0.5.3",
          "numpy>=1.26,<3"]
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install(*PINNED)
         .add_local_dir("memsub", "/root/repo/memsub"))
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
DOMAINS = ("financial", "legal", "code", "literature")
DOMAIN_CAP = 23563   # smallest B.3 domain count (code)


@app.function(image=image, volumes={"/artifacts": artifacts}, timeout=3600,
              memory=16384)
def build_manifest() -> dict:
    import os
    import sys
    sys.path.insert(0, "/root/repo")
    from memsub.certification import (
        assert_train_eval_disjoint,
        build_training_manifest,
        canonical_sha256,
    )
    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        all_items = json.load(f)
    with open("/artifacts/corpus-compactor-train/triplets.json") as f:
        traced_ids = {r["item_id"] for r in json.load(f)}
    holdout_path = (
        "/artifacts/corpus-fullrecipe/certification-holdout-clean-v1.json")
    with open(holdout_path) as f:
        holdout = json.load(f)
    holdout_payload = {k: v for k, v in holdout.items() if k != "sha256"}
    if canonical_sha256(holdout_payload) != holdout["sha256"]:
        raise ValueError("certification holdout hash mismatch")
    holdout_docs = {row["doc_id"] for row in holdout["documents"]}
    built = build_training_manifest(
        all_items, traced_ids=traced_ids, holdout_doc_ids=holdout_docs,
        domains=DOMAINS, domain_cap=DOMAIN_CAP)
    if built["orphan_traced_item_ids"]:
        raise ValueError(
            "traced items outside selected training/holdout sets: "
            f"{built['orphan_traced_item_ids'][:10]}")
    overlap = assert_train_eval_disjoint(
        built["items"], holdout["documents"])
    payload = {
        "domain_cap": DOMAIN_CAP,
        "holdout_sha256": holdout["sha256"],
        "counts": built["counts"],
        "excluded_traced_item_ids": built["excluded_traced_item_ids"],
        "orphan_traced": built["orphan_traced_item_ids"],
        "overlap_audit": overlap,
        "items": built["items"],
    }
    digest = canonical_sha256(payload)
    os.makedirs("/artifacts/corpus-fullrecipe", exist_ok=True)
    with open("/artifacts/corpus-fullrecipe/mixture-manifest.json", "w") as f:
        json.dump({**payload, "sha256": digest}, f)
    artifacts.commit()
    return {"sha256": digest, "holdout_sha256": holdout["sha256"],
            "counts": built["counts"], "total": len(built["items"]),
            "remainder": len(built["remainder_item_ids"]),
            "excluded_traced": len(built["excluded_traced_item_ids"]),
            "orphan_traced": len(built["orphan_traced_item_ids"]),
            "overlap_audit": overlap}


@app.local_entrypoint()
def main():
    print(json.dumps(build_manifest.remote(), indent=2))
