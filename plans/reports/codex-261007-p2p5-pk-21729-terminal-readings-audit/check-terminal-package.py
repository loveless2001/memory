"""Review terminal commit/indexes and preliminary billing. Stream-hashes excluded local binaries only."""
import concurrent.futures
import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
PLAN = Path("plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen")
PKG = ROOT / PLAN / "pk-campaign-terminal"
GROUP = ROOT / PLAN / "p2p5-qwen3-0p6b-screen-v1"
COMMIT = "428fc6d67feef70de47b6dd95569ef0cee7ec76e"
checks = {}
started = time.time()


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def check(name, ok, detail=None):
    checks[name] = {"ok": bool(ok), "detail": detail}
    assert ok, (name, detail)


def entries(path):
    out = {}
    for line in path.read_text().splitlines():
        want, rel = line.split(None, 1)
        assert len(want) == 64 and all(c in "0123456789abcdef" for c in want) and rel not in out
        out[rel] = want
    return out


status = subprocess.check_output(["git", "diff", "--name-status", "a17cd40", COMMIT], text=True).splitlines()
paths = [line.split("\t", 1)[1] for line in status]
check("addition_only_commit_in_scope", all(line.startswith("A\t") for line in status)
      and all(p.startswith(str(PLAN) + "/") for p in paths), {"added_files": len(paths)})
check("no_binary_commits", not any(p.endswith((".pt", ".safetensors")) for p in paths))
parent = subprocess.check_output(["git", "show", "-s", "--format=%P", COMMIT], text=True).strip()
check("expected_terminal_package_parent", parent == "44b1f187d52ab385d5fe11c62df55f256b03ffaa", parent)
dirty = subprocess.check_output(["git", "diff", COMMIT, "--", str(PLAN), "memsub", "scripts", "configs", "modal-runners", "tests"], text=True)
check("package_and_source_clean_against_commit", not dirty)
index = entries(PKG / "SHA256SUMS-terminal-package.txt")
check("metadata_index_matches", len(index) == 3 and all(sha(PKG / rel) == want for rel, want in index.items()), index)
tracked = set(subprocess.check_output(["git", "ls-files", "--", str(GROUP.relative_to(ROOT))], text=True).splitlines())
result_hashes = json.loads((OUT / "saved-results-check.json").read_text())["artifact_hashes"]
check("all_25_terminal_result_files_committed_and_unchanged", len(result_hashes) == 25
      and all(rel in tracked and sha(ROOT / rel) == want for rel, want in result_hashes.items()))
binary_index = entries(PKG / "SHA256SUMS-excluded-binaries-not-in-git.txt")
disk_binaries = {str(p.relative_to(ROOT)) for p in GROUP.rglob("*") if p.is_file() and p.suffix in (".pt", ".safetensors")}
check("binary_index_exactly_covers_untracked_binaries", len(binary_index) == 558 and set(binary_index) == disk_binaries
      and not set(binary_index) & tracked, {"indexed": len(binary_index), "on_disk": len(disk_binaries)})
nonbinary = [p for slot in GROUP.iterdir() if slot.is_dir() and slot.name != "readings"
             for p in (slot / "volume-evidence/collect-1").rglob("*")
             if p.is_file() and p.suffix not in (".pt", ".safetensors")]
check("all_slot_nonbinary_evidence_committed", len(nonbinary) > 0
      and all(str(p.relative_to(ROOT)) in tracked for p in nonbinary), {"files": len(nonbinary), "bytes": sum(p.stat().st_size for p in nonbinary)})

bill = json.loads((PKG / "billing-reconciliation-prelim.json").read_text(), parse_float=Decimal)
source = ROOT / bill["source"]
check("billing_snapshot_sha", sha(source) == bill["source_sha256"], bill["source_sha256"])
raw = json.loads(source.read_text(), parse_float=Decimal)
base = json.loads((OUT.parent / "codex-261007-p2p5-pk-21652-launch-verification/launch-verification.json").read_text())
slot_ids = {s["provenance"]["deployed_app_id"] for s in base["slots"].values()}
read_id, control2, control1 = "ap-MvPw7JVom3vnRTxVVyzldN", "ap-suOdTgdc8PNSfZ3jbnsesa", "ap-eqwdT119XvSoBJC1I2kDqC"
known = slot_ids | {read_id, control2, control1}
sums, selected, excluded = {}, [], []
for row in raw:
    cost = Decimal(row["cost"])
    assert cost.is_finite() and cost >= 0
    if row["description"].startswith("memsub-m4-sgm-p2p5-pk-campaign"):
        assert row["object_id"] in known and row["environment"] == "main"
        assert "2026-10-07T00:00:00" <= row["interval_start"] <= "2026-10-07T17:00:00"
        sums[row["object_id"]] = sums.get(row["object_id"], Decimal(0)) + cost
        selected.append(row)
    else:
        excluded.append(row)
reported_slots = {k.split()[-1]: v for k, v in bill["attempt_2"]["slot_apps"].items()}
check("billing_all_nine_slot_subtotals", set(reported_slots) == slot_ids
      and all(sums[k] == v for k, v in reported_slots.items()), {k: str(v) for k, v in sums.items()})
slot_total = sum((sums[k] for k in slot_ids), Decimal(0))
total = sum(sums.values(), Decimal(0))
check("billing_totals_decimal_exact", slot_total == bill["attempt_2"]["slot_apps_total"]
      and sums[read_id] == bill["attempt_2"][f"readings {read_id}"]
      and sums[control2] == bill["attempt_2"][f"control {control2} (through 17:00 hour)"]
      and sums[control1] == bill["attempt_1"][f"control {control1}"]
      and total == bill["campaign_total_app_attributed"], {"slots": str(slot_total), "readings": str(sums[read_id]),
      "controller_r2": str(sums[control2]), "controller_attempt1": str(sums[control1]), "total": str(total)})
check("unrelated_app_excluded", all(r["object_id"] != "ap-Pu6Dy71P8DakYgOma6JC0A" for r in selected),
      {"selected_rows": len(selected), "excluded_rows": len(excluded), "excluded_app_ids": sorted({r["object_id"] for r in excluded})})
price = json.loads((ROOT / PLAN / "pk6/priced-estimate-v6.json").read_text())
ref = bill["reference"]
check("frozen_reserve_and_estimate_reference", abs(float(ref["conditional_reserve_usd"]) - 259.98622130744764) <= 1e-12
      and abs(float(ref["v6_estimate_usd"]) - 116.31395302286052) <= 1e-12
      and abs(float(ref["reserve_lines"]["readings_app"]) - 16.707700454518204) <= 1e-12)

def binary_hash(item):
    rel, want = item
    p = ROOT / rel
    return rel, sha(p) == want, p.stat().st_size

bad, size, count = [], 0, 0
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(binary_hash, item) for item in binary_index.items()]
    for future in concurrent.futures.as_completed(futures):
        rel, ok, nbytes = future.result()
        count += 1
        size += nbytes
        if not ok:
            bad.append(rel)
        if count % 100 == 0:
            print(json.dumps({"binary_hash_progress": count, "elapsed_s": round(time.time() - started, 1)}), flush=True)
check("all_excluded_binary_payload_hashes_match", count == 558 and not bad,
      {"checked": count, "bytes": size, "gib": size / 1024**3, "mismatches": bad})
result = {"status": "PASS", "checks": checks, "commit": COMMIT,
          "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "billing_app_attributed_preliminary_usd": str(total), "billing_subtotals": {k: str(v) for k, v in sums.items()},
          "billing_source_sha256": sha(source), "metadata_index_sha256": sha(PKG / "SHA256SUMS-terminal-package.txt"),
          "excluded_binary_index_sha256": sha(PKG / "SHA256SUMS-excluded-binaries-not-in-git.txt"),
          "billing_limits": ["snapshot hour still open; later billing may backfill", "controller continued after snapshot",
                            "failed slot-image build not app-attributed", "$8.57 proof hold remains separate",
                            "conditional reserve is not a platform cash ceiling"],
          "elapsed_s": time.time() - started, "remote_mutations": 0, "artifact_edits": 0, "gpu_launches": 0}
(OUT / "terminal-package-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "checks": len(checks), "binary_files": count,
                  "binary_bytes": size, "billing_app_attributed_preliminary_usd": str(total), "elapsed_s": result["elapsed_s"]}))
