"""Read-only saved-evidence check. No model, Modal, or fresh evaluation imports."""
import ast
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "plans/261006-0316-m4-sgm-p2c-filler-length-curriculum"
BUNDLE = BASE / "preflight-r2"
PRODUCER = "8c3161ac90fda21ff1d767a392af2ed08f802ec5"
EVIDENCE_COMMIT = "ada6312b859be481911a829c563d58cac14d719d"
IVS = ("none", "bank_derange", "coord_shuffle", "read_offset", "query_off")
FIELDS = {"batch": int, "episode": int, "episode_hash": str, "query": int,
          "key": int, "label": int, "pred": int, "correct": bool, "intervention": str}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def rows_check(rows):
    assert len(rows) == 5120
    eps = {}
    for row in rows:
        assert set(row) == set(FIELDS)
        assert all(type(row[k]) is t for k, t in FIELDS.items())
        assert 0 <= row["label"] < 64 and 0 <= row["pred"] < 64
        assert row["correct"] == (row["pred"] == row["label"])
        key = row["batch"], row["episode"], row["episode_hash"]
        queries = eps.setdefault(row["intervention"], {}).setdefault(key, {})
        assert row["query"] not in queries
        queries[row["query"]] = row["key"], row["label"]
    assert set(eps) == set(IVS)
    assert all(len(e) == 256 and all(set(q) == {0, 1, 2, 3} for q in e.values()) for e in eps.values())
    assert all(e == eps["none"] for e in eps.values())


report = json.loads((BUNDLE / "preflight.json").read_text())
assert frozen(EVIDENCE_COMMIT, str((BUNDLE / "preflight.json").relative_to(ROOT))) == (BUNDLE / "preflight.json").read_bytes()
assert report["observer"] == report["observer_end"]
identity = report["observer"]
assert identity["git_head"] == PRODUCER
for path, digest in identity["analysis_sha256"].items():
    assert sha(ROOT / path) == digest == hashlib.sha256(frozen(PRODUCER, path)).hexdigest(), path
package_hash = hashlib.sha256()
for path in sorted((ROOT / "memsub").rglob("*.py")):
    if "pycache" in path.parent.name:
        continue
    package_hash.update(str(path.relative_to(ROOT)).encode() + b"\0")
    package_hash.update(path.read_bytes() + b"\0")
assert package_hash.hexdigest() == identity["memsub_source_sha256"]
for path, field in (("configs/m4_sgm_p2c_inputs.json", "inputs_index_sha256"),
                    ("configs/m4_sgm_p2c_grid.json", "grid_sha256")):
    assert sha(ROOT / path) == identity[field]
    assert frozen(PRODUCER, path) == (ROOT / path).read_bytes()
index = json.loads((ROOT / "configs/m4_sgm_p2c_inputs.json").read_text())
grid = json.loads((ROOT / "configs/m4_sgm_p2c_grid.json").read_text())
prereg = index["prereg"]
assert sha(ROOT / prereg["path"]) == prereg["sha256"] == identity["prereg_sha256"]
assert frozen(prereg["commit"], prereg["path"]) == (ROOT / prereg["path"]).read_bytes()
assert index["new_group"]["grid_sha256"] == identity["grid_sha256"]
assert index["new_group"]["group"] == "p2c-filler-curriculum-v1"
assert sorted(report["inputs_validated"]) == sorted(index["reused"]) and len(index["reused"]) == 10
for key, item in index["reused"].items():
    cell = ROOT / item["cell"]
    manifest = json.loads((cell / "run_manifest.json").read_text())
    assert sha(cell / "run_manifest.json") == item["run_manifest_sha256"], key
    assert sha(cell / "trained_parameters.safetensors") == item["trained_parameters_sha256"] == manifest["trained_parameters_sha256"], key
    assert all(manifest[m] == item[i] for m, i in (("git_head", "git_head"),
               ("memsub_source_sha256", "memsub_source_sha256"), ("pilot_config", "pilot_config"),
               ("modal_group", "group"))), key

wanted = {"P-on": {f"v2-n{n}-s{s}" for n in (32, 64) for s in (0, 1)},
          "P-off": {f"filleroff-n{n}-s{s}" for n in (16, 32) for s in (0, 1)}}
assert set(index["parity"]) == set(wanted)
parity = {}
for kind, entries in index["parity"].items():
    assert len(entries) == 4 and {e["checkpoint"] for e in entries} == wanted[kind]
    for entry in entries:
        key = f"{kind}:{entry['checkpoint']}"
        seed = int(entry["checkpoint"].rsplit("s", 1)[1])
        assert entry["seed"] == 9300011 + seed
        assert type(entry["filler_writes"]) is bool and entry["filler_writes"] == (kind == "P-on")
        assert tuple(entry["interventions"]) == IVS
        produced = BUNDLE / f"parity-{kind}-{entry['checkpoint']}-rows.jsonl"
        reference = ROOT / entry["reference"]
        digest = sha(produced)
        assert produced.read_bytes() == reference.read_bytes()
        assert digest == sha(reference) == entry["reference_sha256"]
        assert frozen(EVIDENCE_COMMIT, str(produced.relative_to(ROOT))) == produced.read_bytes()
        rows = [json.loads(line) for line in produced.read_text().splitlines()]
        assert rows == [json.loads(line) for line in reference.read_text().splitlines()]
        rows_check(rows)
        expected = {"rows": 5120, "reference_rows": 5120, "produced_sha256": digest,
                    "reference_sha256": digest, "parsed_equal": True, "byte_equal": True}
        assert report["parity"][key] == expected
        parity[key] = expected
assert set(report["parity"]) == set(parity) | {"pass"} and report["parity"]["pass"] is True
assert len(list(BUNDLE.glob("parity-*-rows.jsonl"))) == 8
assert report["schedule_smoke"] == {"train_filler_lens": [0, 0, 40, 40], "eval_filler_lens": [40],
    "result_label": "tiny-random-lm+taskhead+DIAGNOSTIC-filler-len-schedule", "pass": True}
suite = BASE / "full-suite-8c3161a.txt"
assert sha(suite) == "af9879204954e2ec09b24a77fcfd42d94e98fa51433e64ce0bc90fcf6be02c40"
assert "206 passed in 181.93s" in suite.read_text() and f"EXIT_STATUS=0 HEAD={PRODUCER}" in suite.read_text()
assert frozen(EVIDENCE_COMMIT, str(suite.relative_to(ROOT))) == suite.read_bytes()
runner = ROOT / "modal-runners/modal-m4-sgm-p2c-nonpreemptible-spawn.py"
cap_node = next(x for x in ast.parse(runner.read_text()).body if isinstance(x, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "P2C_CAP_USD" for t in x.targets))
assert ast.literal_eval(cap_node.value) is None
assert (grid["artifact_eval_seed_base"], grid["readings_seed_base"]) == (9300011, 9500011)
assert (index["artifact_eval_seed_base"], index["readings_seed_base"]) == (9300011, 9500011)
assert len(grid["blocks"]) == 1
block = grid["blocks"][0]
assert block == {"tag": "curriculum", "n_bindings": [32, 64], "seeds": [0, 1],
                 "override": {"filler_len_schedule": [[0, 0], [1000, 40]]}}
assert grid["base"]["steps"] == 1500 and grid["base"]["filler_len"] == 40 and grid["base"]["filler_writes"] is True
walls, timeouts = {}, {}
for n in (32, 64):
    for s in (0, 1):
        run = f"curriculum-learned-n{n}-s{s}"
        path = ROOT / f"plans/261005-0210-m4-sgm-p0-p2/runs/p2-load-sweep-v2/main-learned-n{n}-s{s}/metrics.json"
        walls[run] = json.loads(path.read_text())["wall_seconds"]
        timeouts[run] = int(1.4 * walls[run])
assert list(timeouts.values()) == [8773, 6952, 11797, 10809]
rate, cpu_rate = 3 * (4 * .0000131 + 8 * .00000222), 3 * 4 * .0000131
reservation = sum(timeouts.values()) * rate + 4 * 360 * rate + 4 * 420 * rate + .10 * sum(timeouts.values()) * cpu_rate + .30 + 1.50
assert math.isclose(reservation, 11.12716980, rel_tol=0, abs_tol=1e-9) and reservation <= 12
output = {"pass": True, "preflight_report_sha256": sha(BUNDLE / "preflight.json"),
          "producer_commit": PRODUCER, "evidence_commit": EVIDENCE_COMMIT,
          "observer_start_end_equal": True, "source_input_prereg_bindings_pass": True,
          "reused_checkpoints_checked": 10, "parity_fixtures_checked": 8, "parity_rows_checked": 40960,
          "parity": parity, "schedule_smoke": report["schedule_smoke"],
          "full_suite": {"passed": 206, "exit_status": 0, "sha256": sha(suite)},
          "timeouts_s": timeouts, "reservation_usd": reservation, "cap_requested_usd": 12,
          "approved_cap_usd": None, "technical_gate": "CLEARED", "training_authorized": False,
          "checkpoint_evaluations": 0, "training_cells_started": 0, "paid_calls": 0}
path = Path(__file__).with_name("codex-261006-p2c-preflight-r2-independent-checks.json")
path.write_text(json.dumps(output, indent=2) + "\n")
print("PASS", path.name, sha(path))
