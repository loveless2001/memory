"""Independent re-derivation of P2D step2-full-v1-r2 readings from raw rows.

Does NOT import the readings script or the decision-rules module: the
registered rules are re-implemented here from their text so a shared bug
would show up as a mismatch.
"""
import hashlib, json, math, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/lenovo/projects/memory")
P = ROOT / "plans/261005-0210-m4-sgm-p0-p2"
OUT = P / "p2d/step2-full-v1-r2"
V2 = P / "runs/p2-load-sweep-v2-volume-mirror"
REPORT = OUT / "step2-readings.json"
fails = []


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("FAIL", msg)


def rows(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def scores(rs, iv):
    eps = defaultdict(dict)
    for r in rs:
        assert r["correct"] == (r["pred"] == r["label"])
        if r["intervention"] == iv:
            k = (r["batch"], r["episode"], r["episode_hash"])
            assert r["query"] not in eps[k]
            eps[k][r["query"]] = r["correct"]
    assert len(eps) == 256 and all(set(v) == {0, 1, 2, 3} for v in eps.values()), iv
    return {k: sum(v.values()) / 4 for k, v in eps.items()}


def paired(a, b, ia="none", ib="none"):
    sa, sb = scores(a, ia), scores(b, ib)
    assert set(sa) == set(sb)
    d = [sa[k] - sb[k] for k in sa]
    m, hw = statistics.fmean(d), 1.96 * statistics.stdev(d) / math.sqrt(len(d))
    return {"diff": m, "lo": m - hw, "hi": m + hw, "n": len(d)}


def close(x, y, tol=1e-9):
    return abs(x - y) <= tol


def same_ci(mine, theirs, tag):
    for k in ("diff", "lo", "hi"):
        check(close(mine[k], theirs[k]), f"{tag}.{k}: mine {mine[k]} vs report {theirs[k]}")
    check(mine["n"] == theirs["n"], f"{tag}.n")


def repro(per_seed):
    return all(v["diff"] >= 0.05 and v["lo"] > 0 for v in per_seed.values())


def align(g, b):
    out = True
    for l in ("1", "3"):
        out &= any(g[l]["median_distance"][h] < b[l]["median_distance"][h] and g[l]["target_coupling"][h] > 0
                   and g[l]["target_coupling"][h] >= 2 * g[l]["other_coupling"][h] and g[l]["read_spread"][h] >= 1
                   for h in range(2))
    return out


print("report sha", sha(REPORT))
rep = json.loads(REPORT.read_text())
check(sha(REPORT) == "a8ad11020a1c7c45a0ab4428614f61bfabb3b4aeb617084ab07797d7cc7fac16", "report sha != posted")
check(rep["report_status"] == "complete" and not rep["partial_mode"], "status")
check(len(rep["index"]) == 12, "index size")
groups = defaultdict(int)
for rid, ix in rep["index"].items():
    groups[ix["group"]] += 1
    cell = Path(ix["mirror"]) / rid
    for f, h in ix["input_sha256"].items():
        check(sha(cell / f) == h, f"{rid}/{f} mirror hash")
        local = Path(ix["runs"]) / rid / f
        if f.endswith(".jsonl") and local.exists():
            check(sha(local) == h, f"{rid}/{f} local != mirror")
    man = json.loads((cell / "run_manifest.json").read_text())
    check(man.get("modal_group") == ix["group"], f"{rid} manifest group")
print("groups", dict(groups))

# baselines: hashes + geometry recorded once per (N, seed)
base_rows = {}
for key, b in rep["baselines"].items():
    p = OUT / b["rows_file"]
    check(sha(p) == b["rows_sha256"], f"baseline {key} rows hash")
    base_rows[key] = rows(p)
    v2cell = V2 / f"main-learned-n{key[1:].split('-')[0]}-s{key[-1]}"
    check(sha(v2cell / "trained_parameters.safetensors") == b["trained_parameters_sha256"], f"baseline {key} params")

prior = P / "p2d/step2-partial-v1"
for f in sorted(OUT.glob("baseline-*.jsonl")):
    q = prior / f.name
    print("baseline", f.name, "prior-partial:", ("IDENTICAL" if sha(q) == sha(f) else "DIFFERENT") if q.exists() else "n/a")

from safetensors.torch import load_file
import torch

summary = []
for tag, arm in rep["arms"].items():
    for nkey, cell in arm.items():
        per = {}
        for s, r in cell["seeds"].items():
            ix = rep["index"][r["run_id"]]
            mc = Path(ix["mirror"]) / r["run_id"]
            treat = rows(mc / "per_example_results.jsonl")
            check(sha(mc / "per_example_results.jsonl") == r["rows_sha256"], f"{r['run_id']} rows sha")
            base = base_rows[f"{nkey}-s{s}"]
            v = paired(treat, base)
            same_ci(v, r["vs_v2"], f"{r['run_id']}.vs_v2")
            acc = statistics.fmean(scores(treat, "none").values())
            bacc = statistics.fmean(scores(base, "none").values())
            check(close(acc, r["final_accuracy"]) and close(bacc, r["baseline_accuracy"]), f"{r['run_id']} acc")
            der = statistics.fmean(scores(treat, "bank_derange").values())
            pd, po = paired(treat, treat, "none", "bank_derange"), paired(treat, treat, "none", "read_offset")
            mu = r["memory_use"]
            check(close(der, mu["derange_accuracy"]), f"{r['run_id']} derange acc")
            same_ci(pd, mu["none_minus_derange"], f"{r['run_id']}.derange")
            same_ci(po, mu["none_minus_read_offset"], f"{r['run_id']}.read_offset")
            mem = der <= 0.04 and pd["lo"] > 0 and po["lo"] > 0
            check(mem == mu["pass"], f"{r['run_id']} memory pass")
            al = align(r["geometry"], rep["baselines"][f"{nkey}-s{s}"]["geometry"])
            check(al == r["alignment"]["pass"], f"{r['run_id']} alignment pass")
            row = {"v2": v, "mem": mem, "align": al, "acc": acc, "bacc": bacc}
            if tag == "long":
                own = paired(treat, rows(mc / "per_example_results_step1500.jsonl"))
                same_ci(own, r["vs_own_1500"], f"{r['run_id']}.vs_own")
                a = load_file(str(mc / "trained_parameters_step1500.safetensors"))
                b = load_file(str(V2 / f"main-learned-{nkey.lower()}-s{s}" / "trained_parameters.safetensors"))
                teq = set(a) == set(b) and all(torch.equal(a[k], b[k]) for k in a)
                check(teq == r["continuity_1500_vs_v2"]["tensors_equal"], f"{r['run_id']} continuity")
                row.update(own=own, teq=teq)
            per[s] = row
        gain = repro({s: x["v2"] for s, x in per.items()})
        check(gain == cell["reproducible_gain_vs_v2"], f"{tag}{nkey} gain")
        check(all(x["align"] for x in per.values()) == cell["alignment_both_seeds"], f"{tag}{nkey} align")
        check(all(x["mem"] for x in per.values()) == cell["memory_use_both_seeds"], f"{tag}{nkey} mem")
        extra = ""
        if tag == "long":
            og = repro({s: x["own"] for s, x in per.items()})
            check(cell["reading"]["4500_vs_own_1500"].startswith("reproducible") == og, f"{tag}{nkey} own reading")
            extra = f" own_gain={og} own=" + "/".join(f"{per[s]['own']['diff']*100:+.2f}" for s in "01") \
                    + " cont=" + "/".join(str(per[s]['teq']) for s in "01")
        print(f"{tag:9s} {nkey}: vs_v2 " + " / ".join(
            f"s{s} {x['v2']['diff']*100:+.2f}pp [{x['v2']['lo']*100:+.2f},{x['v2']['hi']*100:+.2f}] "
            f"acc {x['bacc']*100:.2f}->{x['acc']*100:.2f} mem={x['mem']} align={x['align']}"
            for s, x in per.items()) + f" | gain={gain}{extra} | {cell['reading']}")

check(not any((P / "p2d/step2-full-v1").iterdir()), "aborted dir not empty")
check(sha(P / "p2d/step2-full-v1.log") == "16d2dd6292658ad7301fcbac6d035af7e418b12d69dafde20c26eac8764cfa4c", "aborted log")
print("FAILS:", len(fails))
sys.exit(1 if fails else 0)
