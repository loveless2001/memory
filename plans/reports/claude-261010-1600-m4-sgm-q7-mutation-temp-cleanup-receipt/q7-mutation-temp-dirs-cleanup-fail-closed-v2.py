"""Fail-closed removal of Q7 ONLY (user #gravity 22634 "Merge and clear Q7"): the 136 `/tmp/b3-mut-*` directories
left by my B3 mutation harness (not evidence). Inventory r3 (eaa018e); target manifest = codex's sealed
`q7-inventory.json` (codex 22613). Q3/Q4/Q5 were NOT selected and are not reachable from this script.

Default = dry run: every check runs, a receipt is written, and no removal API is reached.
`--execute Q7` removes, but only after the same checks pass, and stops at the first failure (recorded durably).

Checks (each must pass, else refuse):
- codex's SHA256SUMS verifies; the inventory/whitelist files match their pinned sha256;
- the live `/tmp/b3-mut-*` set equals the 136 pinned paths exactly (no new or missing dirs);
- each root is a real directory (lstat, not a symlink) with the pinned dev/inode/uid; a no-follow walk finds exactly
  the pinned regular-file count/bytes, only regular files/dirs/symlinks, and exactly the pinned symlinks
  (relative path -> target), every target inside the candidate set;
- no process has its cwd, root or an open fd inside a candidate;
- the 50 retained raw mutation logs (codex `retained-temp-logs/`) exist and match their manifest sha256.
Removal: `shutil.rmtree` (fd-based, does not follow symlinks), then absence is verified.

v2 (codex 22637 REVISE of v1 f5ffa48, kept unchanged): (1) immediately before EACH rmtree, that root's identity/
content/symlink/in-use checks run again against the original candidate set; the first mismatch is recorded and stops
the run. This narrows the check-to-removal gap; it does not give exclusive filesystem access. (2) Receipts are written
atomically (tmp + flush + fsync + os.replace + directory fsync); the path being removed is persisted before removal
and the completed path after it, so a refusal or partial failure leaves a valid receipt."""
import argparse, glob, hashlib, json, os, shutil, stat, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CODEX = REPO / "plans/reports/codex-261010-gravity-22609-cleanup-inventory-r3-audit"
PINNED = {"q7-inventory.json": "ad9b78d0684354d400f25b6b57e0b82d80eff7c47b3d3763eba1f1201686ec48",
          "q7-path-whitelist.json": "29fdfe2a5f0aedd3e082e3d667edc2d544d9aeb7ece31db26fe2ab85f6510cd1"}
N_DIRS, N_FILES, N_BYTES, N_LINKS, N_LOGS = 136, 2554, 52_354_966, 520, 50
PATTERN = "/tmp/b3-mut-*"
OUT = Path(__file__).resolve().parent


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_codex_seal() -> list:
    probs = []
    r = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=CODEX, capture_output=True, text=True)
    if r.returncode != 0:
        probs.append(f"codex SHA256SUMS failed: {r.stdout[-300:]}{r.stderr[-300:]}")
    for name, want in PINNED.items():
        if sha256(CODEX / name) != want:
            probs.append(f"{name} sha mismatch")
    return probs


def walk_tree(root: str) -> tuple:
    """No-follow walk: (regular files, regular bytes, {relative symlink: target}, other-type paths)."""
    files, nbytes, links, other = 0, 0, {}, []
    for d, dirs, names in os.walk(root, followlinks=False):
        for n in dirs + names:
            p = os.path.join(d, n)
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                links[os.path.relpath(p, root)] = os.readlink(p)
            elif stat.S_ISREG(st.st_mode):
                files, nbytes = files + 1, nbytes + st.st_size
            elif not stat.S_ISDIR(st.st_mode):
                other.append(p)
    return files, nbytes, links, other


def check_root(e: dict, roots: set) -> list:
    """Identity, no-follow contents and symlinks of ONE pinned root (symlink targets checked against ALL roots)."""
    p, probs = e["path"], []
    try:
        st = os.lstat(p)
    except OSError as ex:
        return [f"{p}: lstat failed: {type(ex).__name__}"]
    if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino, st.st_uid) != (e["dev"], e["inode"], e["uid"]):
        return [f"{p}: not the pinned directory (mode/dev/inode/uid)"]
    files, nbytes, links, other = walk_tree(p)
    want_links = {s["path"]: s["target"] for s in e["symlinks"]}
    if (files, nbytes) != (e["regular_files"], e["regular_file_bytes"]):
        probs.append(f"{p}: contents changed ({files} files/{nbytes} B vs {e['regular_files']}/{e['regular_file_bytes']})")
    if links != want_links:
        probs.append(f"{p}: symlinks differ from pinned")
    if other:
        probs.append(f"{p}: unexpected file types {other[:3]}")
    for t in links.values():
        if not any(os.path.realpath(os.path.join(p, t)).startswith(r + os.sep) or os.path.realpath(t) == r
                   for r in roots):
            probs.append(f"{p}: symlink target outside candidates: {t}")
    return probs


def check_targets(inv: list) -> list:
    probs, roots = [], {e["path"] for e in inv}
    live = set(glob.glob(PATTERN))
    if live != roots:
        probs.append(f"live set differs: new {sorted(live - roots)[:5]} missing {sorted(roots - live)[:5]}")
    for e in inv:
        if e["path"] in live:
            probs += check_root(e, roots)
    return probs


def check_in_use(roots: set) -> list:
    users = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        cands = [f"/proc/{pid}/cwd", f"/proc/{pid}/root"]
        try:
            cands += [f"/proc/{pid}/fd/{fd}" for fd in os.listdir(f"/proc/{pid}/fd")]
        except OSError:
            pass
        for c in cands:
            try:
                t = os.readlink(c)
            except OSError:
                continue
            if any(t == r or t.startswith(r + os.sep) for r in roots):
                users.append(f"pid {pid}: {t}")
    return [f"in use: {users[:5]}"] if users else []


def check_retained_logs() -> list:
    man = json.loads((CODEX / "temp-log-manifest.json").read_text())
    if len(man) != N_LOGS:
        return [f"retained log manifest has {len(man)} entries, expected {N_LOGS}"]
    bad = [m["retained"] for m in man if sha256(CODEX / m["retained"]) != m["sha256"]]
    return [f"retained logs mismatch: {bad[:3]}"] if bad else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", choices=["Q7"], help="remove the Q7 targets (default: dry run)")
    a = ap.parse_args()
    mode = "execute" if a.execute == "Q7" else "dry_run"
    rec = {"mode": mode, "script": "v2", "selected": ["Q7"], "not_selected_untouched": ["Q3", "Q4", "Q5"],
           "t_start": time.time()}
    rcpt = OUT / f"q7-cleanup-v2-{mode}-receipt.json"

    def save():
        """Atomic durable write: tmp + flush + fsync, os.replace, then fsync the directory."""
        tmp = rcpt.with_name(rcpt.name + ".tmp")
        with open(tmp, "w") as f:
            f.write(json.dumps(rec, indent=2))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, rcpt)
        dfd = os.open(OUT, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    inv = json.loads((CODEX / "q7-inventory.json").read_text())
    white = json.loads((CODEX / "q7-path-whitelist.json").read_text())
    probs = check_codex_seal()
    if sorted(white) != sorted(e["path"] for e in inv) or len(inv) != N_DIRS:
        probs.append("whitelist/inventory disagree or count != 136")
    if (sum(e["regular_files"] for e in inv), sum(e["regular_file_bytes"] for e in inv),
            sum(len(e["symlinks"]) for e in inv)) != (N_FILES, N_BYTES, N_LINKS):
        probs.append("inventory totals differ from pinned totals")
    probs += check_targets(inv) + check_in_use({e["path"] for e in inv}) + check_retained_logs()
    du = subprocess.run(["du", "-sbc", *sorted(glob.glob(PATTERN))], capture_output=True, text=True).stdout
    rec.update(checks_problems=probs, du_before_total=(du.strip().splitlines() or ["0"])[-1], n_targets=len(inv))
    if probs:
        rec["outcome"] = "REFUSED"
        save()
        print(json.dumps({"outcome": "REFUSED", "problems": probs[:10]}))
        return 1
    if mode == "dry_run":
        rec["outcome"] = "DRY_RUN_OK (no removal API reached)"
        save()
        print(json.dumps({"outcome": rec["outcome"], "targets": len(inv), "du_before": rec["du_before_total"]}))
        return 0
    rec["removed"], rec["outcome"], roots = [], "in progress", {e["path"] for e in inv}
    save()
    for e in inv:
        guard = check_root(e, roots) + check_in_use({e["path"]})
        if guard:
            rec.update(removing=None, outcome=f"STOPPED before {e['path']}: per-root guard: {guard[:3]}")
            save()
            print(json.dumps({"outcome": rec["outcome"], "removed": len(rec["removed"])}))
            return 1
        rec["removing"] = e["path"]
        save()
        try:
            shutil.rmtree(e["path"])
        except Exception as ex:
            rec.update(outcome=f"FAILED at {e['path']}: {type(ex).__name__}: {ex}")
            save()
            print(json.dumps({"outcome": rec["outcome"], "removed": len(rec["removed"])}))
            return 1
        rec["removed"].append(e["path"])
        rec["removing"] = None
        save()
    left = [e["path"] for e in inv if os.path.lexists(e["path"])] + sorted(glob.glob(PATTERN))
    rec.update(absent_verified=not left, left=left[:10], t_end=time.time(),
               outcome="REMOVED_VERIFIED" if not left else "REMOVED_BUT_PRESENT")
    save()
    print(json.dumps({"outcome": rec["outcome"], "removed": len(rec["removed"])}))
    return 0 if not left else 1


if __name__ == "__main__":
    sys.exit(main())
