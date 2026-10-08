"""User-approved cleanup (#gravity 22029: "A B C D"). Run from the memory repo root.

A  untracked gen-*.pt (intermediate resume checkpoints) under the closed P2.5 campaign plan dir
B  codex B-review.jsonl (51 probe intermediate checkpoints; step50/100/1500, finals and the damaged +
   supplemental copies are NOT in it)
C  codex C-recommended.jsonl (11,700 generated CPU test/rejection-fixture tensors)
D  git-ignored tensors (.pt/.safetensors/.bin/.npy/.npz) under the July-September 2026 plan dirs (2607*/2609*)

Refuses (skips and reports) any file that is git-tracked, on codex's protected list, bound by the
dead-start diagnosis index, under the running Stage A plan dir, or (for B/C) whose current sha256/bytes
differ from codex's manifest. Writes receipt.jsonl (one row per deleted file) and summary.json beside
this script. Protected files are re-hashed after deletion.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEX = Path("plans/reports/codex-261009-gravity-22023-cleanup-review")
P25 = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
STAGE_A = "plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen"
DIAG_INDEX = Path("plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis/inputs-index.json")
TENSOR = (".pt", ".safetensors", ".bin", ".npy", ".npz")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def git_lines(*args) -> list[str]:
    return [x for x in subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.split("\n") if x]


tracked = set(git_lines("ls-files"))
protected = {e["path"] if isinstance(e, dict) else e for e in json.loads((CODEX / "protected-files.json").read_text())}
protected_sha = {e["path"]: e.get("sha256") for e in json.loads((CODEX / "protected-files.json").read_text()) if isinstance(e, dict)}
diag = {e["params"] for e in json.loads(DIAG_INDEX.read_text())["entries"] if e["params"] != "init"}
diag |= {e["manifest"] for e in json.loads(DIAG_INDEX.read_text())["entries"]}

cand: list[dict] = []
for p in git_lines("ls-files", "--others", "--exclude-standard", "--", P25):
    if Path(p).name.startswith("gen-") and p.endswith(".pt"):
        cand.append({"group": "A", "path": p})
for g, f in (("B", "B-review.jsonl"), ("C", "C-recommended.jsonl")):
    for line in (CODEX / f).read_text().splitlines():
        r = json.loads(line)
        cand.append({"group": g, "path": r["path"], "want_sha256": r["sha256"], "want_bytes": r["bytes"]})
for p in git_lines("ls-files", "--others", "--ignored", "--exclude-standard", "--", "plans"):
    parts = p.split("/")
    if len(parts) > 2 and parts[1][:4] in ("2607", "2609") and p.endswith(TENSOR):
        cand.append({"group": "D", "path": p})

df_before = shutil.disk_usage("/home")
receipt, skipped = [], []
for c in cand:
    p = Path(c["path"])
    why = ("tracked" if c["path"] in tracked else "protected" if c["path"] in protected else
           "diagnosis-bound" if c["path"] in diag else "stage-a" if c["path"].startswith(STAGE_A) else
           "missing" if not p.is_file() else None)
    if why is None:
        size, digest = p.stat().st_size, sha(p)
        if "want_sha256" in c and (digest != c["want_sha256"] or size != c["want_bytes"]):
            why = "differs from codex manifest"
    if why:
        skipped.append({**c, "skipped": why})
        continue
    p.unlink()
    receipt.append({"group": c["group"], "path": c["path"], "bytes": size, "sha256": digest})

after_problems = []
for path, want in protected_sha.items():
    q = Path(path)
    if not q.is_file():
        after_problems.append({"path": path, "problem": "missing after cleanup"})
    elif want and sha(q) != want:
        after_problems.append({"path": path, "problem": "sha changed"})
df_after = shutil.disk_usage("/home")
by = {}
for r in receipt:
    b = by.setdefault(r["group"], {"files": 0, "bytes": 0})
    b["files"] += 1
    b["bytes"] += r["bytes"]
summary = {"approved_by": "user #gravity 22029 (A B C D)", "deleted_by_group": by,
           "deleted_files": len(receipt), "deleted_bytes": sum(r["bytes"] for r in receipt),
           "skipped": skipped, "protected_checked": len(protected_sha), "protected_problems": after_problems,
           "disk_free_before": df_before.free, "disk_free_after": df_after.free}
(HERE / "receipt.jsonl").write_text("".join(json.dumps(r) + "\n" for r in receipt))
(HERE / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps({k: v for k, v in summary.items() if k != "skipped"} | {"skipped_count": len(skipped)}, indent=1))
