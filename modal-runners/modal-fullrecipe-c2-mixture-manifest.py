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
image = modal.Image.debian_slim(python_version="3.12")
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
DOMAINS = ("financial", "legal", "code", "literature")
DOMAIN_CAP = 23563   # smallest B.3 domain count (code)


@app.function(image=image, volumes={"/artifacts": artifacts}, timeout=3600,
              memory=16384)
def build_manifest() -> dict:
    import os
    with open("/artifacts/corpus-mcq-full/all-items.json") as f:
        all_items = json.load(f)
    with open("/artifacts/corpus-compactor-train/triplets.json") as f:
        traced_ids = {r["item_id"] for r in json.load(f)}

    by_domain: dict[str, list[dict]] = {d: [] for d in DOMAINS}
    for it in all_items:
        d = it["doc_id"].split("/")[0]
        by_domain[d].append(it)

    manifest, remainder, counts = [], [], {}
    for d in DOMAINS:
        rows = sorted(by_domain[d], key=lambda i: (i["doc_id"], i["item_id"]))
        sel = rows[:DOMAIN_CAP]
        counts[d] = {"corpus": len(rows), "selected": len(sel),
                     "traced": sum(1 for i in sel
                                   if i["item_id"] in traced_ids)}
        for i in sel:
            has = i["item_id"] in traced_ids
            manifest.append({"item_id": i["item_id"], "doc_id": i["doc_id"],
                             "domain": d, "has_trace": has})
            if not has:
                remainder.append(i["item_id"])

    # traced items NOT selected would break trace reuse — must be zero
    sel_ids = {m["item_id"] for m in manifest}
    orphans = sorted(traced_ids - sel_ids)

    blob = json.dumps(manifest, sort_keys=True).encode()
    digest = hashlib.sha256(blob).hexdigest()
    os.makedirs("/artifacts/corpus-fullrecipe", exist_ok=True)
    with open("/artifacts/corpus-fullrecipe/mixture-manifest.json", "w") as f:
        json.dump({"domain_cap": DOMAIN_CAP, "sha256": digest,
                   "counts": counts, "orphan_traced": orphans,
                   "items": manifest}, f)
    artifacts.commit()
    return {"sha256": digest, "counts": counts, "total": len(manifest),
            "remainder": len(remainder), "orphan_traced": len(orphans)}


@app.local_entrypoint()
def main():
    print(json.dumps(build_manifest.remote(), indent=2))
