"""Independent saved-row arithmetic and CPU episode-hash check. No model or GPU execution."""
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
LOCAL = PLAN / "p2p5-qwen3-0p6b-screen-v1/readings"
EVID = LOCAL / "volume-evidence/collect-1"
READ = EVID / "readings-v1"
CONTROLS = ("memory_off", "single_cell", "random_fixed")
GAIN, LOSS, EXCLUDED, NEITHER = "reproducible gain", "reproducible loss", "positive gain >=5pp excluded", "neither"
ORIGINAL = "unavailable: learned-n32-s1: state FAILED"
checks = {}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def unique(pairs):
    d = {}
    for k, v in pairs:
        assert k not in d, f"duplicate JSON key {k}"
        d[k] = v
    return d


def strict(text):
    return json.loads(text, object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def check(name, ok, detail=None):
    checks[name] = {"ok": bool(ok), "detail": detail}
    assert ok, (name, detail)


def close(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(close(a[k], b[k]) for k in a)
    if type(a) is bool or type(b) is bool:
        return type(a) is bool and type(b) is bool and a == b
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= 1e-12
    return a == b


def episode_scores(rows, iv):
    groups = {}
    for r in rows:
        if r["intervention"] == iv:
            key = r["batch"], r["episode"], r["episode_hash"]
            assert r["query"] not in groups.setdefault(key, {})
            groups[key][r["query"]] = r["correct"]
    assert len(groups) == 256 and all(set(v) == {0, 1, 2, 3} for v in groups.values())
    return {k: sum(v.values()) / 4 for k, v in groups.items()}


def paired(a, b, iva="none", ivb="none"):
    a, b = episode_scores(a, iva), episode_scores(b, ivb)
    assert set(a) == set(b)
    ds = [a[k] - b[k] for k in a]
    mean = statistics.mean(ds)
    hw = 1.96 * statistics.stdev(ds) / math.sqrt(len(ds))
    return {"diff": mean, "lo": mean - hw, "hi": mean + hw, "n": len(ds)}


def classify(per_seed):
    values = list(per_seed.values())
    if all(v["diff"] >= .05 and v["lo"] > 0 for v in values):
        return GAIN
    if all(v["diff"] <= -.05 and v["hi"] < 0 for v in values):
        return LOSS
    if all(v["hi"] < .05 for v in values):
        return EXCLUDED
    return NEITHER


files = [LOCAL / "collect_status.json", LOCAL / "launch_provenance.json", LOCAL / "call.json",
         EVID / "readings-v1.exit.json", READ / "readings.json", *sorted(READ.glob("rows-*.jsonl"))]
before = {str(p.relative_to(ROOT)): sha(p) for p in files}
report = strict((READ / "readings.json").read_text())
prov = strict((LOCAL / "launch_provenance.json").read_text())
collect = strict((LOCAL / "collect_status.json").read_text())
exit_record = strict((EVID / "readings-v1.exit.json").read_text())
call = strict((LOCAL / "call.json").read_text())
prefixes = {"readings.json": "e8764c42", "readings-v1.exit.json": "80a632ad", "collect_status.json": "ba3a5f42",
            "launch_provenance.json": "85932ec5", "call.json": "f591e756"}
check("handoff_hash_prefixes", all(sha(p).startswith(prefixes[p.name]) for p in files if p.name in prefixes))
check("success_and_complete_collection", exit_record["rc"] == 0 and exit_record["stderr_tail"] == ""
      and collect["result"] == {"status": "read", "rc": 0} and collect["poll"] == "result"
      and collect["evidence_complete"] is True and all(x == 0 for x in collect["evidence"].values())
      and collect["final_shutdown"]["status"] == "stopped_verified"
      and collect["call_id"] == call["call_id"] == "fc-01M4BG37XCKFD3A9WRJ91D44MB")
check("report_identity_and_labels", report["identity"] == report["expected"] == prov["expected_identity"]
      and report["end_binding"] == "verified" and report["readings_seed_base"] == 9600011
      and report["campaign_label"] == "post-hoc amended" and set(report["n"]) == {"16", "32"})
spec_path = ROOT / "configs/m4_sgm_p2p5_pk_posthoc_validation_amendment.json"
check("exact_amendment_and_original_outcome", report["posthoc_amendment"] == {
    "label": "post-hoc amended", "cell": "learned-n32-s1", "spec_sha256": sha(spec_path),
    "original_gate": "learned-n32-s1: state FAILED", "original_reading": {"32": ORIGINAL, "16": ORIGINAL}})

grid = strict((ROOT / "configs/m4_sgm_p2p5_grid.json").read_text())
pilots = {}
for block in grid["blocks"]:
    for n in block["n_bindings"]:
        for seed in block["seeds"]:
            cid = f"{block['tag']}-n{n}-s{seed}"
            pilots[cid] = {**grid["base"], **block["override"], "n_bindings": n, "seed": seed}

# Validate the published population using frozen CPU generation and hashes only; no model is loaded.
import torch
from memsub.sgm.synthetic_binding_task import BindingTaskSpec, sample_batch
population = {}
for n in (16, 32):
    for seed in (0, 1):
        gen = torch.Generator().manual_seed(9600011 + seed)
        for bi in range(16):
            batch = sample_batch(BindingTaskSpec(n, 4, 40), "heldout", 16, gen)
            for ep in range(16):
                digest = hashlib.sha256()
                for t in (batch.source[ep], batch.query_keys[ep], batch.labels[ep]):
                    digest.update(t.numpy().tobytes())
                for q in range(4):
                    population[(n, seed, bi, ep, q)] = (digest.hexdigest()[:16], int(batch.query_keys[ep, q]), int(batch.labels[ep, q]))

rows_by, corners, expected_files, total = {}, {}, set(), 0
fields = {"batch": int, "episode": int, "episode_hash": str, "query": int, "key": int,
          "label": int, "pred": int, "correct": bool, "intervention": str}
head_set = {f"L{layer}h{head}" for layer in (6, 13, 20, 27) for head in range(4)}
for n in (32, 16):
    expected_corners = {}
    for cid, pilot in pilots.items():
        if pilot["arm"] == "oracle" or pilot["n_bindings"] == n:
            expected_corners[cid + f"-on-n{n}" if pilot["arm"] == "oracle" else cid] = (cid, pilot)
    check(f"exact_corner_set_n{n}", set(report["n"][str(n)]["corners"]) == set(expected_corners))
    for key, (cid, pilot) in expected_corners.items():
        p = READ / f"rows-{cid}-on-n{n}.jsonl"
        expected_files.add(p.name)
        info = report["n"][str(n)]["corners"][key]
        check("row_sha_" + key, sha(p) == info["rows_sha256"])
        rows = [strict(line) for line in p.read_text().splitlines()]
        ivs = ("none",) if pilot["arm"] == "memory_off" else ("none", "bank_derange", "read_offset")
        seen = set()
        for r in rows:
            assert set(r) == set(fields) and all(type(r[k]) is typ for k, typ in fields.items())
            assert 0 <= r["batch"] < 16 and 0 <= r["episode"] < 16 and 0 <= r["query"] < 4
            assert 0 <= r["pred"] < 64 and r["correct"] == (r["pred"] == r["label"])
            assert r["intervention"] in ivs
            row_key = (r["intervention"], r["batch"], r["episode"], r["query"])
            assert row_key not in seen
            seen.add(row_key)
            assert (r["episode_hash"], r["key"], r["label"]) == population[(n, pilot["seed"], r["batch"], r["episode"], r["query"])]
        assert len(rows) == 1024 * len(ivs) == len(seen)
        acc = {iv: statistics.mean(episode_scores(rows, iv).values()) for iv in ivs}
        check("accuracy_" + key, close(acc["none"], info["accuracy_none"]))
        tele = info["gate_telemetry_descriptive"]
        if pilot["arm"] == "memory_off":
            check("gate_unavailable_" + key, tele == {"status": "unavailable: SGM disabled (local-only control)"})
        else:
            heads = tele["per_head"]
            aucs = [v["auroc_applied"] for v in heads.values() if v["auroc_applied"] is not None]
            means = [v[k] for v in heads.values() for k in ("binding_projected_mean", "binding_effective_mean",
                                                          "filler_projected_mean", "filler_effective_mean")]
            assert all(isinstance(x, (float, int)) and math.isfinite(x) and 0 <= x <= 1 for x in [*aucs, *means])
            assert all(0 <= v[f"{c}_applied_events"] <= 64 * (40 if c == "filler" else 2 * n)
                       for v in heads.values() for c in ("binding", "filler"))
            pooled = sum(v["filler_effective_mean"] for v in heads.values()) / sum(v["binding_effective_mean"] for v in heads.values())
            check("gate_aggregates_" + key, tele["status"] == "measured" and set(heads) == head_set
                  and tele["episodes"] == 64 and tele["events_per_head"] == {"filler": 2560, "binding": 128 * n}
                  and close(pooled, tele["rho_pooled_effective"]) and len(aucs) == tele["auroc_defined_heads"]
                  and close(statistics.mean(aucs), tele["auroc_mean_defined"]) and close(min(aucs), tele["auroc_min_defined"]))
        rows_by[(pilot["arm"], n, pilot["seed"])] = rows
        corners[key] = {"n": n, "arm": pilot["arm"], "seed": pilot["seed"], "accuracy": acc, "rows_sha256": sha(p)}
        total += len(rows)
check("exact_file_and_row_universe", expected_files == {p.name for p in READ.glob("rows-*.jsonl")}
      and len(expected_files) == 20 and total == 53248, {"files": len(expected_files), "rows": total})

readings, memory = {}, {}
for n in (32, 16):
    per_control = {c: {str(seed): paired(rows_by[("learned", n, seed)], rows_by[(c, n, seed)])
                       for seed in (0, 1)} for c in CONTROLS}
    labels = {c: classify(per_control[c]) for c in CONTROLS}
    mem = {}
    for seed in (0, 1):
        rows = rows_by[("learned", n, seed)]
        der = statistics.mean(episode_scores(rows, "bank_derange").values())
        pd, po = paired(rows, rows, ivb="bank_derange"), paired(rows, rows, ivb="read_offset")
        mem[str(seed)] = {"derange_accuracy": der, "none_minus_derange": pd, "none_minus_read_offset": po,
                          "pass": der <= .04 and pd["lo"] > 0 and po["lo"] > 0}
    interface = all(statistics.mean(episode_scores(rows_by[("oracle", n, seed)], "none").values()) >= .5 for seed in (0, 1))
    use = all(m["pass"] for m in mem.values())
    address = "read-address use established" if all(m["none_minus_read_offset"]["lo"] > 0 for m in mem.values()) else "read-address use not established"
    if not interface:
        reading = f"interface not established at N{n}; screen not read"
    elif all(label == GAIN for label in labels.values()):
        reading = f"SCREEN PASS at N{n}" if use else f"gain over every control without registered memory use at N{n}"
    else:
        reading = f"screen not passed at N{n}; per-control labels: " + ", ".join(f"{c}={labels[c]}" for c in CONTROLS)
    expected = {"interface": interface, "per_control": per_control, "labels": labels, "memory_use": use,
                "read_address": address, "reading": reading, "label": "post-hoc amended", "original_reading": ORIGINAL}
    actual = {k: v for k, v in report["n"][str(n)].items() if k != "corners"}
    check(f"all_statistics_flags_labels_reading_n{n}", close(expected, actual))
    readings[str(n)], memory[str(n)] = expected, mem

# Fresh closure/identity and real 18-cell binding, without calling parity or loading any model.
s = importlib.util.spec_from_file_location("codex_saved_rd", ROOT / "scripts/sgm-p2p5-pk-campaign-readings.py")
rd = importlib.util.module_from_spec(s)
s.loader.exec_module(rd)
check("current_source_and_manifest_match_report", rd.current_identity() == report["identity"]
      and rd.binding_problem(report["expected"]) is None)
local_baseline = strict((OUT.parent / "codex-261007-p2p5-pk-21710-amendment-audit/local-audit.json").read_text())
check("frozen_spec_still_matches_approved_audit", sha(spec_path) == report["posthoc_amendment"]["spec_sha256"]
      and local_baseline["status"] == "PASS")

after = {str(p.relative_to(ROOT)): sha(p) for p in files}
check("results_unchanged_during_audit", before == after)
result = {"status": "PASS", "checks": checks, "artifact_hashes": before, "corners": corners,
          "readings": readings, "memory_use_by_seed": memory,
          "population_hashes_verified": True, "row_count": total, "row_files": len(expected_files),
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "limitations": ["raw descriptive gate events were not saved; aggregates checked against saved per-head summaries",
                          "parity and execution order inferred from rc0 and successful report under the frozen implementation, not replayed"],
          "model_evaluations": 0, "gpu_launches": 0, "remote_mutations": 0, "artifact_edits": 0}
(OUT / "saved-results-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "checks": len(checks), "row_files": len(expected_files), "rows": total,
                  "readings": {n: r["reading"] for n, r in readings.items()}, "memory_use_by_seed": memory,
                  "completed_utc": result["completed_utc"]}))
