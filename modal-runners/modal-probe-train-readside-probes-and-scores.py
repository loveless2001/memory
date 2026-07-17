"""PROBE arms c2 (hidden-state layer sweep + best-layer MLP) and
c1-demoted (per-head attention-stat probe), trained volume-side on the
unified capture shards. Emits per-item scores for every captured item
(split-tagged) so all downstream analyses (stack, p3, GT22-25) run
locally without re-touching the GPU.

Splits: sha256 doc bucket — train <0.6, val [0.6, 0.7), test >= 0.7
(test identical to c0's split for comparability).

Outputs:
  /artifacts/probe/readside-scores.npz
    item_ids, split (0/1/2), y, c2_lin (best layer), c2_mlp (3-seed
    mean), c1d, layer curves (val/test AUC per layer)
  /artifacts/probe/readside-metrics.json

Usage:
  modal run --detach modal-runners/modal-probe-train-readside-probes-and-scores.py
"""

import json

import modal

PINNED = ["torch==2.7.1", "numpy>=1.26,<3"]
app = modal.App("memsub-probe-train")
image = modal.Image.debian_slim(python_version="3.12").pip_install(*PINNED)
artifacts = modal.Volume.from_name("memsub-artifacts", create_if_missing=True)
VOLUMES = {"/artifacts": artifacts}


@app.function(image=image, gpu="L4", volumes=VOLUMES, timeout=14400,
              memory=65536, cpu=8)
def train_probes() -> dict:
    import glob
    import hashlib

    import numpy as np
    import torch

    def auc(y_true, s):
        order = np.argsort(s)
        r = np.empty(len(s))
        r[order] = np.arange(1, len(s) + 1)
        # average ranks for ties
        _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
        sums = np.zeros(len(cnt))
        np.add.at(sums, inv, r)
        r = sums[inv] / cnt[inv]
        pos = y_true == 1
        n1, n0 = pos.sum(), (~pos).sum()
        return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

    ids, y, attn0, hidden, p2 = [], [], [], [], []
    for npz_path in sorted(glob.glob("/artifacts/probe/capture-*.npz")):
        st_path = npz_path.replace(".npz", ".state.json")
        with open(st_path) as f:
            rows = {r["item_id"]: r for r in json.load(f)["rows"]}
        try:
            z = np.load(npz_path)
            # materialize once per shard: NpzFile.__getitem__ decompresses
            # the whole array on EVERY access — per-item indexing is
            # quadratic
            z_ids, z_attn, z_hid = z["item_ids"], z["attn_stats"], z["hidden"]
        except Exception as e:
            print(f"SKIPPING unreadable shard {npz_path}: {e}", flush=True)
            continue
        for k, iid in enumerate(z_ids):
            r = rows[str(iid)]
            ids.append(str(iid))
            y.append(r["y"])
            p2.append(r["p2_insufficient"])
            attn0.append(z_attn[k][0])                   # [36, 32, 6] step 0
            hidden.append(z_hid[k])                      # [37, 2560]
    y = np.array(y)
    p2 = np.array(p2, dtype=np.float32)
    attn0 = np.stack(attn0).astype(np.float32).reshape(len(ids), -1)
    hidden = np.stack(hidden).astype(np.float32)
    print(f"assembled {len(ids)} items, y+ {y.mean():.3f}")

    def bucket(iid):
        doc = iid[4:].rsplit("_", 2)[0]
        return int(hashlib.sha256(doc.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    b = np.array([bucket(i) for i in ids])
    split = np.where(b < 0.6, 0, np.where(b < 0.7, 1, 2))
    # multihop rows (item_id 'mh:...') are score-only: their y is a
    # different regime (eviction-based needed flag); never trained on
    is_mh = np.array([i.startswith("mh:") for i in ids])
    split = np.where(is_mh, 3, split)
    tr, va, te = split == 0, split == 1, split == 2
    dev = "cuda"
    y_tr_t = torch.tensor(y[tr], dtype=torch.float32, device=dev)

    def fit_logistic(X, mask_tr, steps=400, lr=0.05, wd=1e-4, seed=0):
        torch.manual_seed(seed)
        mu = X[mask_tr].mean(0)
        sd = X[mask_tr].std(0) + 1e-6
        Xn = torch.tensor((X - mu) / sd, dtype=torch.float32, device=dev)
        w = torch.zeros(X.shape[1], device=dev, requires_grad=True)
        c = torch.zeros(1, device=dev, requires_grad=True)
        opt = torch.optim.AdamW([w, c], lr=lr, weight_decay=wd)
        Xtr = Xn[mask_tr]
        for _ in range(steps):
            opt.zero_grad()
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                Xtr @ w + c, y_tr_t)
            loss.backward()
            opt.step()
        with torch.no_grad():
            s = (Xn @ w + c).cpu().numpy()
        return s

    # ---- c2 layer sweep (linear, convex -> single fit per layer) ---------
    curve_val, curve_test, best = [], [], (-1, -1.0)
    scores_by_layer = {}
    for li in range(hidden.shape[1]):
        s = fit_logistic(hidden[:, li], tr)
        av, at = auc(y[va], s[va]), auc(y[te], s[te])
        curve_val.append(round(av, 4))
        curve_test.append(round(at, 4))
        scores_by_layer[li] = s
        if av > best[1]:
            best = (li, av)
        print(f"layer {li}: val {av:.4f} test {at:.4f}", flush=True)
    best_layer = best[0]
    c2_lin = scores_by_layer[best_layer]

    # ---- best-layer MLP, 3 seeds ----------------------------------------
    X = hidden[:, best_layer]
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Xn = torch.tensor((X - mu) / sd, dtype=torch.float32, device=dev)
    mlp_scores, mlp_test_aucs = [], []
    for seed in (0, 1, 2):
        torch.manual_seed(seed)
        net = torch.nn.Sequential(
            torch.nn.Linear(X.shape[1], 256), torch.nn.GELU(),
            torch.nn.Dropout(0.1), torch.nn.Linear(256, 1)).to(dev)
        opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)
        best_va, best_state, patience = -1, None, 0
        for epoch in range(200):
            net.train()
            perm = torch.randperm(int(tr.sum()), device=dev)
            Xtr = Xn[tr][perm]
            ytr = y_tr_t[perm]
            for i in range(0, len(perm), 4096):
                opt.zero_grad()
                loss = torch.nn.functional.binary_cross_entropy_with_logits(
                    net(Xtr[i:i + 4096]).squeeze(-1), ytr[i:i + 4096])
                loss.backward()
                opt.step()
            net.eval()
            with torch.no_grad():
                sv = net(Xn[va]).squeeze(-1).cpu().numpy()
            av = auc(y[va], sv)
            if av > best_va:
                best_va, patience = av, 0
                best_state = [p.detach().clone() for p in net.parameters()]
            else:
                patience += 1
                if patience >= 20:
                    break
        with torch.no_grad():
            for p, bp in zip(net.parameters(), best_state):
                p.copy_(bp)
            s = net(Xn).squeeze(-1).cpu().numpy()
        mlp_scores.append(s)
        mlp_test_aucs.append(auc(y[te], s[te]))
    c2_mlp = np.mean(mlp_scores, axis=0)

    # ---- c1-demoted: per-head attention stats ---------------------------
    c1d = fit_logistic(attn0, tr)

    out = {
        "n": len(ids), "split_sizes": [int(tr.sum()), int(va.sum()),
                                       int(te.sum())],
        "c2_layer_curve_val": curve_val, "c2_layer_curve_test": curve_test,
        "c2_best_layer": int(best_layer),
        "c2_lin_test_auc": round(auc(y[te], c2_lin[te]), 4),
        "c2_mlp_test_auc_mean": round(float(np.mean(mlp_test_aucs)), 4),
        "c2_mlp_test_auc_sd": round(float(np.std(mlp_test_aucs)), 4),
        "c1d_test_auc": round(auc(y[te], c1d[te]), 4),
        "p2_test_auc": round(auc(y[te], p2[te]), 4),
    }
    np.savez_compressed(
        "/artifacts/probe/readside-scores.npz",
        item_ids=np.array(ids), split=split, y=y,
        c2_lin=c2_lin, c2_mlp=c2_mlp, c1d=c1d, p2=p2,
        curve_val=np.array(curve_val), curve_test=np.array(curve_test),
        best_layer=best_layer)
    with open("/artifacts/probe/readside-metrics.json", "w") as f:
        json.dump(out, f, indent=1)
    artifacts.commit()
    print(json.dumps(out, indent=1))
    return out
