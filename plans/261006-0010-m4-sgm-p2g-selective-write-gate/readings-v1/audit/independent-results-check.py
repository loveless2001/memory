"""Independent P2G result audit. Reuses saved rows; never evaluates fresh seed.

Interval/classifier/half-oracle/memory-use and gate statistics are implemented
here with stdlib arithmetic, separately from the registered rules. Gate events
are gathered only on development seed 4242 using the bound observer.
"""
import bisect
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "plans/261006-0010-m4-sgm-p2g-selective-write-gate/readings-v1"
REPORT = json.loads((BUNDLE / "p2g-readings.json").read_text())
INDEX = json.loads((ROOT / "configs/m4_sgm_p2g_inputs.json").read_text())
OUT = Path(__file__).with_name("codex-261006-p2g-results-independent-audit.json")
RESULT = {"report_sha256": hashlib.sha256((BUNDLE / "p2g-readings.json").read_bytes()).hexdigest(),
          "reserved_seed_re_evaluations": 0, "dev_seed": 4242, "n": {}, "gate_checks": {}}
GAIN, LOSS, EXCLUDED, NEITHER = ("reproducible gain", "reproducible loss", "positive gain >=5pp excluded", "neither")
FIELDS = {"batch": int, "episode": int, "episode_hash": str, "query": int,
          "key": int, "label": int, "pred": int, "correct": bool, "intervention": str}
IVS = {"none", "bank_derange", "read_offset"}
SLOTS = {"Ton-Eon": ("on", "on"), "Ton-Eoff": ("on", "off"),
         "Toff-Eoff": ("off", "off"), "Toff-Eon": ("off", "on"), "Tgate-Eon": ("gate", "on")}


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
    assert REPORT["artifact_eval_seed_base"] == 9300011 and REPORT["readings_seed_base"] == 9400011
    assert observer["git_head"] == "2613ced101810bd248c1d82d1c3b83d994076120"
    for p, h in observer["analysis_sha256"].items():
        frozen = subprocess.run(["git", "show", observer["git_head"] + ":" + p], capture_output=True, check=True).stdout
        assert hashlib.sha256(frozen).hexdigest() == h == sha(ROOT / p)
    assert observer["grid_sha256"] == sha(ROOT / "configs/m4_sgm_p2g_grid.json")
    assert observer["inputs_index_sha256"] == sha(ROOT / "configs/m4_sgm_p2g_inputs.json")
    pkg = ROOT / "memsub"
    digest = hashlib.sha256()
    for p in sorted(pkg.rglob("*.py")):
        if "pycache" in p.parent.name:
            continue
        digest.update(str(p.relative_to(pkg.parent)).encode() + b"\0")
        digest.update(p.read_bytes() + b"\0")
    assert digest.hexdigest() == observer["memsub_source_sha256"]
    runs = ROOT / "plans/261005-0210-m4-sgm-p0-p2/runs/p2g-selective-write-v1"
    assert REPORT["launch"] == json.loads((runs / "launch_provenance.json").read_text())
    for key, ref in INDEX["reused"].items():
        cell = ROOT / ref["cell"]
        assert sha(cell / "run_manifest.json") == ref["run_manifest_sha256"]
        assert sha(cell / "trained_parameters.safetensors") == ref["trained_parameters_sha256"]
        m = json.loads((cell / "run_manifest.json").read_text())
        for k in ("git_head", "memsub_source_sha256", "pilot_config", "trained_parameters_sha256"):
            assert m[k] == ref[k]
        assert m["modal_group"] == ref["group"]
    for key, ref in REPORT["p2g_cells"].items():
        cell = ROOT / ref["cell"]
        for field, name in (("run_manifest_sha256", "run_manifest.json"), ("trained_parameters_sha256", "trained_parameters.safetensors"), ("rows_sha256", "per_example_results.jsonl")):
            assert sha(cell / name) == ref[field]
    keys = set()
    for kind, entries in INDEX["parity"].items():
        for e in entries:
            key = f"{kind}:{e['checkpoint']}"
            keys.add(key)
            path = BUNDLE / "parity" / f"parity-{kind}-{e['checkpoint']}-rows.jsonl"
            b = path.read_bytes()
            assert b == (ROOT / e["reference"]).read_bytes() and sha(path) == e["reference_sha256"]
            p = REPORT["parity"][key]
            assert len(b.splitlines()) == p["rows"] == p["reference_rows"] == 5120
            assert p["parsed_equal"] is True and p["byte_equal"] is True and p["produced_sha256"] == sha(path)
    assert len(keys) == 6 and set(REPORT["parity"]) == keys | {"pass"} and REPORT["parity"]["pass"] is True
    RESULT["provenance_and_parity_pass"] = True


def statistics_audit():
    for n in ("16", "32"):
        seed_results = {}
        for s in ("0", "1"):
            rr = REPORT["n"][n]["seeds"][s]
            scores, targets, corners = {}, {}, {}
            assert set(rr["corners"]) == set(SLOTS)
            for slot, (t, e) in SLOTS.items():
                path = BUNDLE / f"rows-n{n}-s{s}-T{t}-E{e}.jsonl"
                assert sha(path) == rr["corners"][slot]["rows_sha256"]
                scores[slot], targets[slot] = row_scores(path)
                role = {"on": "T_on", "off": "T_off", "gate": "gate"}[t]
                key = INDEX["corners"][n][role].format(s=s)
                expected_cell = REPORT["p2g_cells"][key[4:]]["cell"] if key.startswith("p2g:") else INDEX["reused"][key]["cell"]
                assert rr["corners"][slot]["source_cell"] == expected_cell
                corners[slot] = {"accuracy_none": float(statistics.mean(scores[slot]["none"].values())), "memory_use": memory(scores[slot])}
                for k, value in corners[slot].items():
                    compare(value, rr["corners"][slot][k], f"N{n}s{s}.{slot}.{k}")
            assert all(t == targets["Ton-Eon"] for t in targets.values())
            nn, nf, ff, fn, gate = (scores[k]["none"] for k in ("Ton-Eon", "Ton-Eoff", "Toff-Eoff", "Toff-Eon", "Tgate-Eon"))
            q2 = {"C_T|off": paired(ff, nf), "C_T|on": paired(fn, nn),
                  "C_E|Ton": paired(nf, nn), "C_E|Toff": paired(ff, fn),
                  "interaction_descriptive": linear([ff, nf, fn, nn], (1.0, -1.0, -1.0, 1.0))}
            q1 = {"gate_vs_v2": paired(gate, nn), "oracle_vs_v2": paired(ff, nn),
                  "half_oracle": linear([gate, nn, ff], (1.0, -.5, -.5)),
                  "rho": rr["corners"]["Tgate-Eon"]["gate"]["rho_pooled_effective"],
                  "memory_use_pass": corners["Tgate-Eon"]["memory_use"]["pass"]}
            compare(q2, rr["q2"], f"N{n}s{s}.q2")
            compare(q1, rr["q1"], f"N{n}s{s}.q1")
            seed_results[s] = {"corners": corners, "q1": q1, "q2": q2}
        labels = {k: label([seed_results[s]["q2"][k] for s in ("0", "1")]) for k in ("C_T|off", "C_T|on", "C_E|Ton", "C_E|Toff")}
        gain = label([v["q1"]["gate_vs_v2"] for v in seed_results.values()])
        oracle = label([v["q1"]["oracle_vs_v2"] for v in seed_results.values()])
        sup = all(v["q1"]["rho"] <= .20 for v in seed_results.values())
        mem = all(v["q1"]["memory_use_pass"] for v in seed_results.values())
        half = all(v["q1"]["half_oracle"]["lo"] > 0 for v in seed_results.values()) if oracle == GAIN else None
        flags = {"gate_vs_v2": gain, "oracle_vs_v2": oracle, "suppression": sup, "memory_use": mem, "half": half}
        compare(labels, REPORT["n"][n]["q2_labels"], f"N{n}.q2_labels")
        compare(flags, REPORT["n"][n]["q1_flags"], f"N{n}.q1_flags")
        assert labels["C_T|off"] == labels["C_T|on"] == GAIN and labels["C_E|Ton"] != GAIN
        assert REPORT["n"][n]["q2_reading"] == "reproducible gain for the no-filler-write training recipe at both eval settings; eval-setting conjunction not met"
        expected = "reproducible gain without registered pooled suppression; mechanism unresolved" if gain == GAIN and not sup else f"no reproducible gain and no registered pooled suppression; gate-v2 contrast is {gain}"
        assert REPORT["n"][n]["q1_reading"] == expected
        RESULT["n"][n] = {"seeds": seed_results, "q1_flags": flags, "q2_labels": labels}
    RESULT["saved_rows_checked"] = 20 * 3072
    RESULT["paired_statistics_and_registered_labels_pass"] = True


def auroc(pos, neg):
    if not pos or not neg:
        return None
    sorted_neg = sorted(neg)
    wins = sum(bisect.bisect_left(sorted_neg, x) + .5 * (bisect.bisect_right(sorted_neg, x) - bisect.bisect_left(sorted_neg, x)) for x in pos)
    return wins / (len(pos) * len(neg))


def gate_audit():
    obs = load(ROOT / "scripts/sgm-p2g-common-observer-evaluation.py", "codex_dev_observer")
    import torch
    torch.set_num_threads(4)
    for n, item in REPORT["n"].items():
        for s, seed in item["seeds"].items():
            for slot, c in seed["corners"].items():
                print(f"DEV4242 gate audit N{n} s{s} {slot}", flush=True)
                cell = ROOT / c["source_cell"]
                man = json.loads((cell / "run_manifest.json").read_text())
                pcfg, backend, _head = obs.load_checkpoint(man["pilot_config"], cell / "trained_parameters.safetensors")
                events = obs.gate_events(backend, pcfg, SLOTS[slot][1] == "on")
                assert set(events) == {(1, 0), (1, 1), (3, 0), (3, 1)}
                expected_counts = {"filler": 64 * 40, "binding": 64 * 2 * int(n)}
                heads, fill, bind, aucs = {}, [], [], []
                for (layer, h), ev in sorted(events.items()):
                    for cls, count in expected_counts.items():
                        a = ev[cls]
                        assert len(a["projected"]) == len(a["effective"]) == count
                        assert all(math.isfinite(x) and 0 <= x <= 1 for k in ("projected", "effective", "applied") for x in a[k])
                        applied = cls == "binding" or SLOTS[slot][1] == "on"
                        assert a["applied"] == (a["effective"] if applied else [])
                        assert applied or all(x == 0 for x in a["effective"])
                    auc = auroc(ev["binding"]["applied"], ev["filler"]["applied"])
                    aucs.append(auc)
                    fill.extend(ev["filler"]["effective"])
                    bind.extend(ev["binding"]["effective"])
                    heads[f"L{layer}h{h}"] = {"auroc_applied": auc,
                        **{f"{cls}_{k}_mean": sum(ev[cls][k]) / len(ev[cls][k]) for cls in ("binding", "filler") for k in ("projected", "effective")},
                        **{f"{cls}_applied_events": len(ev[cls]["applied"]) for cls in ("binding", "filler")}}
                assert len(fill) == 10240 and len(bind) == 64 * 2 * int(n) * 4 and statistics.mean(bind) > 0
                defined = [x for x in aucs if x is not None]
                actual = {"episodes": 64, "events_per_head": expected_counts,
                          "rho_pooled_effective": (sum(fill) / len(fill)) / (sum(bind) / len(bind)),
                          "auroc_mean_defined": sum(defined) / len(defined) if defined else None,
                          "auroc_min_defined": min(defined) if defined else None,
                          "auroc_defined_heads": len(defined), "per_head": heads}
                compare(actual, c["gate"], f"N{n}s{s}.{slot}.gate")
                RESULT["gate_checks"][f"N{n}s{s}.{slot}"] = actual
    RESULT["gate_development_summaries_pass"] = True


if __name__ == "__main__":
    try:
        provenance()
        statistics_audit()
        print("Saved-row statistics and provenance PASS", flush=True)
        gate_audit()
        provenance()
        RESULT["pass"] = True
    except Exception as e:
        RESULT["pass"] = False
        RESULT["error"] = repr(e)
        raise
    finally:
        OUT.write_text(json.dumps(RESULT, indent=2) + "\n")
    print("AUDIT PASS", sha(OUT), flush=True)
