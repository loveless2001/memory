"""Independent P2C results audit: saved rows and development telemetry only.

Stdlib intervals, ordered classifier, half-reference, memory-use and reading
logic are independent of the registered rules. No reserved-seed evaluation.
Run at the canonical plans/reports path. --saved-only avoids all model replay.
"""
import argparse
import bisect
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum/readings-v1"
REPORT = json.loads((BUNDLE / "p2c-readings.json").read_text())
INDEX = json.loads((ROOT / "configs/m4_sgm_p2c_inputs.json").read_text())
OUT = Path(__file__).with_name("codex-261006-p2c-results-independent-audit.json")
RESULT = {"report_sha256": hashlib.sha256((BUNDLE / "p2c-readings.json").read_bytes()).hexdigest(),
          "reserved_seed_re_evaluations": 0, "dev_seed": 4242, "n": {}, "gate_checks": {}}
GAIN, LOSS, EXCLUDED, NEITHER = ("reproducible gain", "reproducible loss", "positive gain >=5pp excluded", "neither")
FIELDS = {"batch": int, "episode": int, "episode_hash": str, "query": int,
          "key": int, "label": int, "pred": int, "correct": bool, "intervention": str}
IVS = {"none", "bank_derange", "read_offset"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p, name):
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def compare(a, b, path):
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), (path, "keys")
        for k in a:
            compare(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, float):
        assert isinstance(b, (int, float)) and not isinstance(b, bool)
        assert math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=0, abs_tol=1e-12), (path, a, b)
    else:
        assert type(a) is type(b) and a == b, (path, a, b)


def row_scores(path):
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    assert len(rows) == 3072
    assert {(r["batch"], r["episode"]) for r in rows} == {(b, e) for b in range(16) for e in range(16)}
    eps, targets = {}, {}
    for r in rows:
        assert set(r) == set(FIELDS) and all(type(r[k]) is t for k, t in FIELDS.items())
        assert 0 <= r["pred"] < 64 and 0 <= r["label"] < 64 and r["correct"] == (r["pred"] == r["label"])
        assert r["intervention"] in IVS
        ep = (r["batch"], r["episode"], r["episode_hash"])
        queries = eps.setdefault(r["intervention"], {}).setdefault(ep, {})
        assert r["query"] not in queries
        queries[r["query"]] = r["correct"]
        target_key = (*ep, r["query"])
        target = (r["key"], r["label"])
        assert targets.get(target_key, target) == target
        targets[target_key] = target
    assert set(eps) == IVS
    assert all(len(v) == 256 and all(set(q) == {0, 1, 2, 3} for q in v.values()) for v in eps.values())
    assert all(set(v) == set(eps["none"]) for v in eps.values())
    return {iv: {k: sum(q.values()) / 4 for k, q in v.items()} for iv, v in eps.items()}, targets


def linear(scores, coeffs):
    assert len(scores) == len(coeffs) and all(set(s) == set(scores[0]) for s in scores)
    d = [sum(c * s[k] for c, s in zip(coeffs, scores)) for k in sorted(scores[0])]
    assert len(d) == 256
    mean = statistics.mean(d)
    hw = 1.96 * statistics.stdev(d) / math.sqrt(len(d))
    return {"diff": float(mean), "lo": mean - hw, "hi": mean + hw, "n": len(d)}


def paired(a, b):
    return linear([a, b], (1.0, -1.0))


def memory(scores):
    d = statistics.mean(scores["bank_derange"].values())
    der = paired(scores["none"], scores["bank_derange"])
    off = paired(scores["none"], scores["read_offset"])
    return {"derange_accuracy": float(d), "none_minus_derange": der, "none_minus_read_offset": off,
            "pass": d <= .04 and der["lo"] > 0 and off["lo"] > 0}


def label(seeds):
    assert len(seeds) == 2
    if all(x["diff"] >= .05 and x["lo"] > 0 for x in seeds):
        return GAIN
    if all(x["diff"] <= -.05 and x["hi"] < 0 for x in seeds):
        return LOSS
    if all(x["hi"] < .05 for x in seeds):
        return EXCLUDED
    return NEITHER


def provenance():
    observer = REPORT["observer"]
    assert observer == REPORT["observer_end"]
    assert REPORT["artifact_eval_seed_base"] == INDEX["artifact_eval_seed_base"] == 9300011
    assert REPORT["readings_seed_base"] == INDEX["readings_seed_base"] == 9500011
    assert observer["git_head"] == "d47fe170c69b035c79e05a17a77f20ebf79aa5de"
    for p, h in observer["analysis_sha256"].items():
        frozen = subprocess.run(["git", "show", observer["git_head"] + ":" + p], cwd=ROOT, capture_output=True, check=True).stdout
        assert hashlib.sha256(frozen).hexdigest() == h == sha(ROOT / p), p
    for key, p in (("grid_sha256", "configs/m4_sgm_p2c_grid.json"),
                   ("inputs_index_sha256", "configs/m4_sgm_p2c_inputs.json"),
                   ("prereg_sha256", INDEX["prereg"]["path"])):
        assert observer[key] == sha(ROOT / p)
        frozen = subprocess.run(["git", "show", observer["git_head"] + ":" + p], cwd=ROOT, capture_output=True, check=True).stdout
        assert hashlib.sha256(frozen).hexdigest() == observer[key]
    prereg = INDEX["prereg"]
    frozen = subprocess.run(["git", "show", prereg["commit"] + ":" + prereg["path"]], cwd=ROOT, capture_output=True, check=True).stdout
    assert hashlib.sha256(frozen).hexdigest() == prereg["sha256"] == observer["prereg_sha256"]
    pkg, digest = ROOT / "memsub", hashlib.sha256()
    for p in sorted(pkg.rglob("*.py")):
        if "pycache" in p.parent.name:
            continue
        digest.update(str(p.relative_to(pkg.parent)).encode() + b"\0")
        digest.update(p.read_bytes() + b"\0")
        frozen = subprocess.run(["git", "show", observer["git_head"] + ":" + str(p.relative_to(ROOT))], cwd=ROOT, capture_output=True, check=True).stdout
        assert p.read_bytes() == frozen
    assert digest.hexdigest() == observer["memsub_source_sha256"]
    runs = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2c-filler-curriculum-v1"
    launch = REPORT["launch"]
    assert launch == json.loads((runs / "launch_provenance.json").read_text())
    assert launch["git_head"] == observer["git_head"]
    for k in ("memsub_source_sha256", "grid_sha256", "inputs_index_sha256", "prereg_sha256"):
        assert launch[k] == observer[k]
    assert launch["runner_sha256"] == observer["analysis_sha256"]["modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py"]
    assert launch["artifact_eval_seed_base"] == 9300011 and launch["readings_seed_base_reserved"] == 9500011
    assert launch["ledger"]["admitted"] is True and launch["ledger"]["cap_usd"] == 12.0
    for key, ref in INDEX["reused"].items():
        cell = ROOT / ref["cell"]
        assert sha(cell / "run_manifest.json") == ref["run_manifest_sha256"]
        assert sha(cell / "trained_parameters.safetensors") == ref["trained_parameters_sha256"]
        m = json.loads((cell / "run_manifest.json").read_text())
        for k in ("git_head", "memsub_source_sha256", "pilot_config", "trained_parameters_sha256"):
            assert m[k] == ref[k], (key, k)
        assert m["modal_group"] == ref["group"]
    assert set(REPORT["p2c_cells"]) == {f"curriculum-learned-n{n}-s{s}" for n in (32, 64) for s in (0, 1)}
    for key, ref in REPORT["p2c_cells"].items():
        cell = ROOT / ref["cell"]
        for field, name in (("run_manifest_sha256", "run_manifest.json"), ("trained_parameters_sha256", "trained_parameters.safetensors"), ("rows_sha256", "per_example_results.jsonl")):
            assert sha(cell / name) == ref[field]
        m = json.loads((cell / "run_manifest.json").read_text())
        cfg = m["pilot_config"]
        assert m["modal_group"] == "p2c-filler-curriculum-v1" and m["git_head"] == observer["git_head"]
        assert m["memsub_source_sha256"] == observer["memsub_source_sha256"]
        assert cfg["steps"] == 1500 and cfg["filler_len"] == 40 and cfg["filler_len_schedule"] == [[0, 0], [1000, 40]]
        assert cfg["filler_writes"] is True and cfg["aux_address_lambda"] == 0 and cfg["checkpoint_steps"] == []
        assert cfg["batch"] == 16 and cfg["lr"] == .003 and cfg["n_queries"] == 4
        assert key == f"curriculum-learned-n{cfg['n_bindings']}-s{cfg['seed']}"
        assert m["final_eval_seed"] == 9300011 + cfg["seed"]
    keys = set()
    for kind, entries in INDEX["parity"].items():
        for e in entries:
            key = f"{kind}:{e['checkpoint']}"
            keys.add(key)
            path = BUNDLE / "parity" / f"parity-{kind}-{e['checkpoint']}-rows.jsonl"
            b = path.read_bytes()
            assert b == (ROOT / e["reference"]).read_bytes() and sha(path) == e["reference_sha256"]
            p = REPORT["parity"][key]
            compare({"rows": 5120, "reference_rows": 5120, "produced_sha256": sha(path),
                     "reference_sha256": e["reference_sha256"], "parsed_equal": True, "byte_equal": True}, p, key)
            assert len(b.splitlines()) == 5120
    assert len(keys) == 8 and set(REPORT["parity"]) == keys | {"pass"} and REPORT["parity"]["pass"] is True
    RESULT["provenance_and_parity_pass"] = True


def reading(gain, mem, half):
    if gain != GAIN:
        return f"no reproducible gain; curriculum-v2 contrast is {gain}"
    if not mem:
        return "reproducible gain without registered memory-use evidence"
    if half is True:
        return "SUPPORTS: the label-free filler-length curriculum reproducibly beats v2 at N and recovers >= half of the filler-off-training reference"
    if half is False:
        return "reproducible gain with memory use; >= half reference recovery not established"
    return "reproducible gain with memory use; reference comparison unavailable (reference prerequisite not met)"


def statistics_audit():
    assert set(REPORT["n"]) == {"32", "64"}
    for n in ("32", "64"):
        seed_results = {}
        assert set(REPORT["n"][n]["seeds"]) == {"0", "1"}
        for s in ("0", "1"):
            rr = REPORT["n"][n]["seeds"][s]
            scores, targets, corners = {}, {}, {}
            assert set(rr["corners"]) == {"v2", "reference", "curriculum"}
            for role in ("v2", "reference", "curriculum"):
                path = BUNDLE / f"rows-n{n}-s{s}-{role}.jsonl"
                assert sha(path) == rr["corners"][role]["rows_sha256"]
                scores[role], targets[role] = row_scores(path)
                key = INDEX["corners"][n][role].format(s=s)
                expected_cell = REPORT["p2c_cells"][key[4:]]["cell"] if key.startswith("p2c:") else INDEX["reused"][key]["cell"]
                assert rr["corners"][role]["source_cell"] == expected_cell
                cfg = json.loads((ROOT / expected_cell / "run_manifest.json").read_text())["pilot_config"]
                assert cfg["n_bindings"] == int(n) and cfg["seed"] == int(s)
                corners[role] = {"accuracy_none": float(statistics.mean(scores[role]["none"].values())), "memory_use": memory(scores[role])}
                for k, value in corners[role].items():
                    compare(value, rr["corners"][role][k], f"N{n}s{s}.{role}.{k}")
            assert all(t == targets["v2"] for t in targets.values())
            cur, v2, ref = (scores[k]["none"] for k in ("curriculum", "v2", "reference"))
            contrasts = {"curriculum_vs_v2": paired(cur, v2), "reference_vs_v2": paired(ref, v2),
                         "half_reference": linear([cur, v2, ref], (1.0, -.5, -.5))}
            for k, value in contrasts.items():
                compare(value, rr[k], f"N{n}s{s}.{k}")
            telemetry = ROOT / rr["corners"]["curriculum"]["source_cell"] / "routing_telemetry.jsonl"
            curve = [[r["step"], r["eval"]["accuracy"]] for r in map(json.loads, telemetry.read_text().splitlines()) if "eval" in r]
            assert [p[0] for p in curve] == list(range(0, 1501, 100))
            assert all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for _, v in curve)
            compare(curve, rr["curriculum_dev_curve_descriptive"], f"N{n}s{s}.dev_curve")
            seed_results[s] = {"corners": corners, **contrasts, "curriculum_dev_curve_descriptive": curve}
        gain = label([v["curriculum_vs_v2"] for v in seed_results.values()])
        reference = label([v["reference_vs_v2"] for v in seed_results.values()])
        mem = all(v["corners"]["curriculum"]["memory_use"]["pass"] for v in seed_results.values())
        half = all(v["half_reference"]["lo"] > 0 for v in seed_results.values()) if reference == GAIN else None
        flags = {"curriculum_vs_v2": gain, "reference_vs_v2": reference, "memory_use": mem, "half": half}
        expected_reading = reading(gain, mem, half)
        compare(flags, REPORT["n"][n]["flags"], f"N{n}.flags")
        assert expected_reading == REPORT["n"][n]["reading"]
        RESULT["n"][n] = {"seeds": seed_results, "flags": flags, "reading": expected_reading}
    joint = all(v["reading"].startswith("SUPPORTS") for v in RESULT["n"].values())
    compare(joint, REPORT["both_n_support_descriptive"], "both_n_support_descriptive")
    RESULT["both_n_support_descriptive"] = joint
    RESULT["saved_rows_checked"] = 12 * 3072
    RESULT["paired_statistics_and_registered_labels_pass"] = True


def auroc(pos, neg):
    if not pos or not neg:
        return None
    sorted_neg = sorted(neg)
    wins = sum(bisect.bisect_left(sorted_neg, x) + .5 * (bisect.bisect_right(sorted_neg, x) - bisect.bisect_left(sorted_neg, x)) for x in pos)
    return wins / (len(pos) * len(neg))


def gate_audit():
    obs = load(ROOT / "scripts/sgm-p2g-common-observer-evaluation.py", "codex_p2c_dev_observer")
    import torch
    torch.set_num_threads(4)
    for n, item in REPORT["n"].items():
        for s, seed in item["seeds"].items():
            for role, c in seed["corners"].items():
                print(f"DEV4242 gate audit N{n} s{s} {role}", flush=True)
                cell = ROOT / c["source_cell"]
                man = json.loads((cell / "run_manifest.json").read_text())
                pcfg, backend, _head = obs.load_checkpoint(man["pilot_config"], cell / "trained_parameters.safetensors")
                events = obs.gate_events(backend, pcfg, True)
                assert set(events) == {(1, 0), (1, 1), (3, 0), (3, 1)}
                expected_counts = {"filler": 64 * 40, "binding": 64 * 2 * int(n)}
                heads, fill, bind, aucs = {}, [], [], []
                for (layer, h), ev in sorted(events.items()):
                    for cls, count in expected_counts.items():
                        a = ev[cls]
                        assert len(a["projected"]) == len(a["effective"]) == len(a["applied"]) == count
                        assert all(math.isfinite(x) and 0 <= x <= 1 for k in ("projected", "effective", "applied") for x in a[k])
                        assert a["applied"] == a["effective"] == a["projected"]
                    auc = auroc(ev["binding"]["applied"], ev["filler"]["applied"])
                    aucs.append(auc)
                    fill.extend(ev["filler"]["effective"])
                    bind.extend(ev["binding"]["effective"])
                    heads[f"L{layer}h{h}"] = {"auroc_applied": auc,
                        **{f"{cls}_{k}_mean": sum(ev[cls][k]) / len(ev[cls][k]) for cls in ("binding", "filler") for k in ("projected", "effective")},
                        **{f"{cls}_applied_events": len(ev[cls]["applied"]) for cls in ("binding", "filler")}}
                assert len(fill) == 10240 and len(bind) == 64 * 2 * int(n) * 4 and statistics.mean(bind) > 0
                actual = {"episodes": 64, "events_per_head": expected_counts,
                          "rho_pooled_effective": (sum(fill) / len(fill)) / (sum(bind) / len(bind)),
                          "auroc_mean_defined": sum(aucs) / len(aucs),
                          "auroc_min_defined": min(aucs), "auroc_defined_heads": 4, "per_head": heads}
                compare(actual, c["gate"], f"N{n}s{s}.{role}.gate")
                RESULT["gate_checks"][f"N{n}s{s}.{role}"] = actual
    RESULT["gate_development_summaries_pass"] = True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--saved-only", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    try:
        provenance()
        statistics_audit()
        print("Saved-row statistics and provenance PASS", flush=True)
        if not args.saved_only:
            gate_audit()
        else:
            RESULT["gate_development_summaries_replayed"] = False
        provenance()
        RESULT["audit_mode"] = "saved-only" if args.saved_only else "saved-plus-development"
        RESULT["pass"] = True
    except Exception as e:
        RESULT["pass"] = False
        RESULT["error"] = repr(e)
        raise
    finally:
        args.out.write_text(json.dumps(RESULT, indent=2) + "\n")
    print("AUDIT PASS", sha(args.out), flush=True)
