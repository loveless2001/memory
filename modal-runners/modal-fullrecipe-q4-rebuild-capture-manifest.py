"""FULLRECIPE Q4 — rebuild the probe capture manifest under the full-recipe
compactor's labels. Item set, pilot flags and in_e1 flags are IDENTICAL to
the instance-A manifest (comparability with the 0.85/0.76 arm table); only
y (and pred/raw bookkeeping) comes from the new GT16-protocol relabel.

Reads  /artifacts/probe/capture-manifest.json
       /artifacts/compactor-gate-labels-fullrecipe/*/slice-*.state.json
Writes /artifacts/probe/capture-manifest-fullrecipe.json

Usage:
  modal run modal-runners/modal-fullrecipe-q4-rebuild-capture-manifest.py
"""

import json

import modal

app = modal.App("memsub-fullrecipe-q4-manifest")
image = modal.Image.debian_slim(python_version="3.12")
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)


@app.function(image=image, volumes={"/artifacts": artifacts}, timeout=3600,
              memory=16384)
def rebuild(labels_base: str =
            "/artifacts/compactor-gate-labels-fullrecipe",
            out_path: str =
            "/artifacts/probe/capture-manifest-fullrecipe.json",
            pred_key: str = "pred_compact_fullrecipe") -> dict:
    import glob
    with open("/artifacts/probe/capture-manifest.json") as f:
        manifest = json.load(f)
    new = {}
    for path in sorted(glob.glob(
            f"{labels_base}/*/slice-*.state.json")):
        with open(path) as f:
            for r in json.load(f)["rows"]:
                new[r["item_id"]] = r
    missing, flipped = [], 0
    out = []
    for m in manifest:
        r = new.get(m["item_id"])
        if r is None:
            missing.append(m["item_id"])
            continue
        row = dict(m)
        row["y_instanceA"] = m["y"]
        row["y"] = r["y_still"]
        row[pred_key] = r["pred_compact_still"]
        flipped += int(r["y_still"] != m["y"])
        out.append(row)
    with open(out_path, "w") as f:
        json.dump(out, f)
    artifacts.commit()
    return {"items": len(out), "missing_from_relabel": len(missing),
            "y_rate_new": sum(r["y"] for r in out) / max(len(out), 1),
            "y_rate_A": sum(r["y_instanceA"] for r in out) / max(len(out), 1),
            "label_flips": flipped}


@app.function(image=image, volumes={"/artifacts": artifacts}, timeout=3600,
              memory=16384)
def population_stats(labels_base: str =
                     "/artifacts/compactor-gate-labels-fullrecipe") -> dict:
    """(domain, y) counts over evicted rows of a relabel base —
    GT22 natural-prevalence weights."""
    import glob
    from collections import Counter
    pop = Counter()
    n_all = n_ev = 0
    for path in sorted(glob.glob(
            f"{labels_base}/*/slice-*.state.json")):
        with open(path) as f:
            for r in json.load(f)["rows"]:
                n_all += 1
                if r["evicted_still"] == 1:
                    n_ev += 1
                    pop[f"{r['domain']}|{r['y_still']}"] += 1
    return {"n_all_rows": n_all, "n_evicted": n_ev,
            "frac_evicted": n_ev / max(n_all, 1), "pop": dict(pop)}


@app.local_entrypoint()
def main(labels_base: str = "/artifacts/compactor-gate-labels-fullrecipe",
         out_path: str = "/artifacts/probe/capture-manifest-fullrecipe.json",
         pred_key: str = "pred_compact_fullrecipe"):
    print(json.dumps(rebuild.remote(labels_base, out_path, pred_key),
                     indent=1))


@app.local_entrypoint()
def pop_stats(labels_base: str = "/artifacts/compactor-gate-labels-fullrecipe"):
    print(json.dumps(population_stats.remote(labels_base), indent=1))
