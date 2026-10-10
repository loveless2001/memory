"""M4-SGM frozen-Qwen line cleanup (inventory r2: claude-261010-0022-m4-sgm-qwen-line-cleanup-inventory-r2.md).

Run ONCE from the memory repo root, ONLY after the user approved the IDs in #gravity:
    .venv/bin/python plans/reports/claude-261010-0030-m4-sgm-qwen-line-cleanup-receipt/qwen-line-cleanup-approved-q1-q3-q4.py Q1 Q3 Q4
Accepted IDs: Q1 (memory/.venv-gpu), Q3 (Modal Volume memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1),
Q4 (the 38 Modal Dicts frozen in codex's q4-name-whitelist.json). Q2 and memsub-artifacts are never touched.

Fail-closed rechecks immediately before each deletion (codex 22364):
  * no active Modal app;
  * codex backups intact: every Q3 mirror file and Q4 export file still matches its recorded sha256;
  * Q3: the live recursive listing equals q3-remote-list-before.json exactly;
  * Q4: each whitelisted Dict still has the exported object_id, and its live items, typed-JSON encoded with
    codex's encoder, equal the exported items exactly;
  * Q1: no running process uses .venv-gpu.
Any failed check aborts BEFORE that ID's deletion and is recorded. Writes receipt.jsonl + summary.json here
(always, also on failure). `--dry-run` runs every precheck/verification read-only and writes dry-run-*.json instead.
"""
import datetime
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
REVIEW = ROOT / "plans/reports/codex-261010-gravity-22360-closing-cleanup-review"
PY = str(ROOT / ".venv/bin/python")
VOL = "memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1"
VENV_GPU = ROOT / ".venv-gpu"
ALLOWED = {"Q1", "Q3", "Q4"}


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def modal_json(*args):
    return json.loads(subprocess.check_output([PY, "-m", "modal", *args, "--json"], text=True))


def run(*args) -> dict:
    p = subprocess.run([PY, "-m", "modal", *args], capture_output=True, text=True, timeout=300)
    return {"argv": list(args), "rc": p.returncode, "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]}


def load_codex_encoder():
    """Reuse codex's exact typed-JSON encoder without executing its capture side effects."""
    src = (REVIEW / "capture-readonly.py").read_text()
    head = src.split("apps = cli(")[0]              # imports + helper defs only
    ns: dict = {"__file__": str(REVIEW / "capture-readonly.py"), "__name__": "codex_encoder"}
    exec(compile(head.replace("OUT.mkdir(parents=True, exist_ok=True)", ""), "codex-encoder", "exec"), ns)
    return ns["encode"]


def main():
    dry = "--dry-run" in sys.argv
    ids = [a for a in sys.argv[1:] if a != "--dry-run"]
    assert ids and set(ids) <= ALLOWED and len(set(ids)) == len(ids), f"approved IDs must be a subset of {ALLOWED}: {ids}"
    assert (ROOT / ".git").exists() and REVIEW.is_dir(), "run from the memory repo root"
    receipt, out = [], {"start_utc": now(), "approved_ids": ids, "dry_run": dry, "results": {}}

    def rec(**row):
        row["utc"] = now(); receipt.append(row); print(json.dumps(row)[:300])

    try:
        body(ids, dry, rec, out)
        out["status"] = "OK"
    except BaseException as e:                              # record and re-raise; nothing after the failure runs
        out["status"] = f"ABORTED: {type(e).__name__}: {e}"
        raise
    finally:
        out["end_utc"] = now()
        pre = "dry-run-" if dry else ""
        (HERE / f"{pre}receipt.jsonl").write_text("".join(json.dumps(r) + "\n" for r in receipt))
        (HERE / f"{pre}summary.json").write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps(out, indent=1))


def body(ids, dry, rec, out):

    # Global prechecks: no active app; codex backups intact.
    apps = modal_json("app", "list")
    active = [a for a in apps if a.get("State", a.get("state")) not in ("stopped",)]
    assert not active, f"active Modal apps: {active}"
    for row in json.loads((REVIEW / "q3-file-verification.json").read_text()):
        p = REVIEW / "q3-complete-volume" / row["path"].lstrip("/")
        assert p.is_file() and sha(p) == row["sha256"], f"Q3 mirror mismatch: {p}"
    exports = {e["name"]: e for e in json.loads((REVIEW / "q4-export-index.json").read_text())}
    for name, e in exports.items():
        assert sha(REVIEW / "q4-dicts" / f"{name}.json") == e["sha256"], f"Q4 export mismatch: {name}"
    rec(step="prechecks", active_apps=0, q3_mirror="intact", q4_exports="intact")

    if "Q4" in ids:
        import modal
        encode = load_codex_encoder()
        names = json.loads((REVIEW / "q4-name-whitelist.json").read_text())
        assert len(names) == 38 and set(names) == set(exports), "whitelist/export index mismatch"
        for name in names:                                   # verify ALL before deleting ANY
            d = modal.Dict.from_name(name, create_if_missing=False)
            live = [{"key": encode(k), "value": encode(v)} for k, v in d.items()]
            doc = json.loads((REVIEW / "q4-dicts" / f"{name}.json").read_text())
            assert d.object_id == exports[name]["object_id"], f"object id changed: {name}"
            assert live == doc["items"], f"content changed since export: {name}"
        rec(step="Q4-verify", dicts=len(names), result="unchanged since codex export")
        for name in ([] if dry else names):
            r = run("dict", "delete", name, "--yes")
            rec(step="Q4-delete", name=name, object_id=exports[name]["object_id"], **r)
            assert r["rc"] == 0, f"delete failed: {name}"
        if not dry:
            left = {x["name"] for x in modal_json("dict", "list")} & set(names)
            assert not left, f"Dicts still present: {left}"
        out["results"]["Q4"] = {"deleted": 0 if dry else len(names), "verified_absent": not dry}

    if "Q3" in ids:
        import modal
        vol = modal.Volume.from_name(VOL, create_if_missing=False)
        live = sorted([{"path": x.path, "type": x.type.name, "mtime": x.mtime, "size": x.size}
                       for x in vol.iterdir("/", recursive=True)], key=lambda x: x["path"])
        assert live == json.loads((REVIEW / "q3-remote-list-before.json").read_text()), "Q3 listing changed since mirror"
        rec(step="Q3-verify", files=sum(x["type"] == "FILE" for x in live), result="listing identical to mirror capture")
        if dry:
            out["results"]["Q3"] = {"deleted": None, "verified": "listing identical"}
        else:
            r = run("volume", "delete", VOL, "--yes")
            rec(step="Q3-delete", volume=VOL, **r)
            assert r["rc"] == 0, "volume delete failed"
            assert VOL not in {x["name"] for x in modal_json("volume", "list")}, "volume still listed"
            out["results"]["Q3"] = {"deleted": VOL, "verified_absent": True}

    if "Q1" in ids:
        users = subprocess.run(["bash", "-c", f"ps -eo args | grep -F '{VENV_GPU}/' | grep -v grep"],
                               capture_output=True, text=True).stdout.strip()
        assert not users, f".venv-gpu in use: {users}"
        assert VENV_GPU.is_dir() and not VENV_GPU.is_symlink(), "unexpected .venv-gpu state"
        size = int(subprocess.check_output(["du", "-sb", str(VENV_GPU)], text=True).split()[0])
        free0 = shutil.disk_usage(ROOT).free
        if dry:
            rec(step="Q1-verify", path=str(VENV_GPU), bytes=size, in_use=False)
            out["results"]["Q1"] = {"deleted": None, "bytes": size}
            return
        shutil.rmtree(VENV_GPU)
        assert not VENV_GPU.exists()
        rec(step="Q1-delete", path=str(VENV_GPU), bytes=size, disk_free_before=free0, disk_free_after=shutil.disk_usage(ROOT).free)
        out["results"]["Q1"] = {"deleted": str(VENV_GPU), "bytes": size, "metadata": str(REVIEW / "q1-gpu-environment.json")}



if __name__ == "__main__":
    main()
