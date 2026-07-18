"""FOLLOWUP F3 + F2 support, extracted volume-side from the existing PROBE
capture shards (no GPU, no re-forward).

F3 sink-head monitor inputs: from each capture shard's attn_stats (step 0,
last-prompt token) pull the 4 inventory heads' latent-mass (idx 0) and
sink-mass (idx 1) => 8 scalars/item:
  L25/H14, L26/H26, L28/H19, L35/H15  x  {m_lat, m_sink}

F2 zero-shot probe: refit the layer-30 linear logistic on the question-
conditioned residual (hidden[:,30]) over the TRAIN split (reproduces c2_lin
~0.819) and save its weights so the LOCAL analysis can apply it zero-shot to
the context-only residuals from the F1/F2 GPU run.

Splits recomputed from item_id doc bucket, identical to the PROBE train
runner (train <0.6, val [0.6,0.7), test >=0.7; mh rows -> split 3).

Outputs under /artifacts/probe/:
  followup-f3-headfeats.npz    item_ids, feats [N,8], y, split, domain, p2
  followup-f2-zeroshot-probe.npz  mu,sd,w,c (layer-30, fit on train),
                                  train/val/test AUC sanity

Usage:
  modal run --detach modal-runners/modal-followup-f3-headfeats-and-f2-zeroshot-probe.py
"""

import glob
import hashlib
import json

import modal

PINNED = ["numpy>=1.26,<3", "scikit-learn==1.5.2"]
app = modal.App("memsub-followup-f3")
image = modal.Image.debian_slim(python_version="3.12").pip_install(*PINNED)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/artifacts": artifacts}

# 4 inventory heads (layer, head); each contributes m_lat (idx0) + m_sink (idx1)
HEADS = [(25, 14), (26, 26), (28, 19), (35, 15)]
LAYER30 = 30


def _bucket(iid: str) -> float:
    doc = iid[4:].rsplit("_", 2)[0]
    return int(hashlib.sha256(doc.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


@app.function(image=image, volumes=VOLUMES, timeout=3600, memory=65536, cpu=8)
def extract() -> dict:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    ids, y, p2, dom = [], [], [], []
    feats, hid30 = [], []
    for npz_path in sorted(glob.glob("/artifacts/probe/capture-*.npz")):
        st = npz_path.replace(".npz", ".state.json")
        with open(st) as f:
            rows = {r["item_id"]: r for r in json.load(f)["rows"]}
        try:
            z = np.load(npz_path)
            z_ids, z_attn, z_hid = z["item_ids"], z["attn_stats"], z["hidden"]
        except Exception as e:
            print(f"skip {npz_path}: {e}", flush=True)
            continue
        for k, iid in enumerate(z_ids):
            iid = str(iid)
            if iid.startswith("mh:"):
                continue                       # score-only regime, skip F3
            r = rows[iid]
            a0 = z_attn[k][0]                  # [36, 32, 6] step-0
            fv = []
            for (li, hh) in HEADS:
                fv.append(float(a0[li, hh, 0]))   # m_lat
                fv.append(float(a0[li, hh, 1]))   # m_sink
            feats.append(fv)
            hid30.append(z_hid[k][LAYER30].astype(np.float32))
            ids.append(iid)
            y.append(int(r["y"]))
            p2.append(float(r["p2_insufficient"]))
            dom.append(r["domain"])
    ids = np.array(ids)
    y = np.array(y)
    feats = np.array(feats, dtype=np.float32)
    hid30 = np.stack(hid30)
    p2 = np.array(p2, dtype=np.float32)
    dom = np.array(dom)
    b = np.array([_bucket(i) for i in ids])
    split = np.where(b < 0.6, 0, np.where(b < 0.7, 1, 2))
    tr, va, te = split == 0, split == 1, split == 2
    print(f"assembled {len(ids)} non-mh items; y+ {y.mean():.3f}; "
          f"splits {tr.sum()}/{va.sum()}/{te.sum()}", flush=True)

    np.savez_compressed(
        "/artifacts/probe/followup-f3-headfeats.npz",
        item_ids=ids, feats=feats, y=y, split=split, domain=dom, p2=p2)

    # ---- F2 zero-shot probe: layer-30 linear logistic on train split -----
    mu, sd = hid30[tr].mean(0), hid30[tr].std(0) + 1e-6
    Xn = (hid30 - mu) / sd
    clf = LogisticRegression(C=1.0, max_iter=2000)
    clf.fit(Xn[tr], y[tr])
    s = clf.decision_function(Xn)
    sanity = {"train_auc": round(float(roc_auc_score(y[tr], s[tr])), 4),
              "val_auc": round(float(roc_auc_score(y[va], s[va])), 4),
              "test_auc": round(float(roc_auc_score(y[te], s[te])), 4)}
    np.savez_compressed(
        "/artifacts/probe/followup-f2-zeroshot-probe.npz",
        mu=mu.astype(np.float32), sd=sd.astype(np.float32),
        w=clf.coef_[0].astype(np.float32), c=np.float32(clf.intercept_[0]),
        **{k: v for k, v in sanity.items()})
    artifacts.commit()
    print("F2 zero-shot probe (question-conditioned) sanity:", sanity,
          flush=True)
    return {"n": int(len(ids)), "f2_probe_sanity": sanity}


@app.local_entrypoint()
def main():
    print(extract.remote())
