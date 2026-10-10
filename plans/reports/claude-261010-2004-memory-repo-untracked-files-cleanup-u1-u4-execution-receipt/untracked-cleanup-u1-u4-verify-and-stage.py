"""Execute untracked-files cleanup U1-U4 (user #gravity 22735 "All"; proposal r2 240b814 + r2.1 a5be502, codex PASS
22725) up to staging. Zero deletions. Does NOT commit: the owner commits after this script reports STAGED_OK.

Steps (stop at first failure, receipt written either way):
1. codex review 22715 seal verifies; U1/U2/U4 text + U3 binaries match path/size/sha256 (all files hashed in full).
2. Append two commented sections to `.gitignore`: codex's U3 (142) and U4 (265) exact rules, verbatim.
3. `git add` U1+U2 paths and the codex review dir; `git add -f` the 1,197 U4 records (they sit in ignored roots).
4. Staged set must equal U1 ∪ U2 ∪ U4 ∪ review-dir files ∪ {.gitignore} exactly (added files + modified .gitignore)."""
import hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

R1 = "plans/reports/claude-261010-1925-memory-repo-untracked-files-cleanup-proposal"
C = "plans/reports/codex-261010-gravity-22715-untracked-proposal-audit"
OUT = Path(__file__).resolve().parent
RCPT = OUT / "verify-and-stage-receipt.json"
MARK = "# --- untracked cleanup U3/U4 (user 22735) ---"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(*a, stdin=None):
    r = subprocess.run(["git", *a], input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(a[:3])} rc={r.returncode}: {r.stderr[-300:]}")
    return r.stdout


def mismatches(recs):
    bad = []
    for r in recs:
        p = r["path"]
        if not os.path.isfile(p) or os.path.islink(p):
            bad.append(f"{p}: missing or not a regular file")
        elif os.path.getsize(p) != r["bytes"] or sha256(p) != r["sha256"]:
            bad.append(f"{p}: size/sha256 differ")
    return bad


def add(paths, force=False):
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("\0".join(paths) + "\0")
    try:
        git("add", *(["-f"] if force else []), "--pathspec-from-file", f.name, "--pathspec-file-nul")
    finally:
        os.unlink(f.name)


def main():
    rec = {"selected": ["U1", "U2", "U3", "U4"], "user_msg": 22735, "deletions": 0, "head": git("rev-parse", "HEAD").strip()}

    def finish(outcome, code):
        rec["outcome"] = outcome
        RCPT.write_text(json.dumps(rec, indent=1))
        print(json.dumps({k: rec[k] for k in ("outcome", "head")}))
        return code

    lists = {n: json.load(open(f"{R1}/{f}")) for n, f in (("U1", "u1-claude-files.json"),
             ("U2", "u2-run-text-files-to-commit.json"), ("U3", "u3-run-binaries-local-only.json"))}
    lists["U4"] = json.load(open(f"{C}/u4-top-level-text-records-to-commit.json"))
    rec["counts"] = {k: len(v) for k, v in lists.items()}
    seal = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=C, capture_output=True, text=True)
    bad = ([] if seal.returncode == 0 else [f"codex review seal failed: {seal.stdout[-200:]}"])
    for k in ("U1", "U2", "U3", "U4"):
        bad += mismatches(lists[k])
    rec["verify_problems"] = bad[:20]
    if bad:
        return finish("REFUSED at verify", 1)
    if git("diff", "--cached", "--name-only").strip() or git("status", "--porcelain", "--untracked-files=no").strip():
        return finish("REFUSED: tracked tree or index not clean before staging", 1)

    gi = Path(".gitignore").read_text()
    if MARK in gi:
        return finish("REFUSED: .gitignore already has the U3/U4 section", 1)
    u3 = Path(f"{C}/u3-proposed-exact-ignore-rules.txt").read_text()
    u4 = Path(f"{C}/u4-proposed-exact-ignore-rules.txt").read_text()
    Path(".gitignore").write_text(
        gi.rstrip("\n") + "\n\n" + MARK + "\n"
        + f"# U3: 142 local-only run binaries (exact paths; sha256 in {R1}/u3-run-binaries-local-only.json)\n" + u3
        + f"# U4: retained codex audit contents, 265 exact roots ({C}); their top-level text records are tracked\n" + u4)

    review = sorted(str(Path(C) / f) for f in os.listdir(C))
    add([r["path"] for r in lists["U1"] + lists["U2"]] + review + [".gitignore"])
    add([r["path"] for r in lists["U4"]], force=True)

    expected = {r["path"] for k in ("U1", "U2", "U4") for r in lists[k]} | set(review) | {".gitignore"}
    staged = git("-c", "core.quotepath=false", "diff", "--cached", "--name-status", "-z").split("\0")
    pairs = dict(zip(staged[1::2], staged[0::2]))
    rec["staged_n"], rec["expected_n"] = len(pairs), len(expected)
    rec["staged_minus_expected"] = sorted(set(pairs) - expected)[:10]
    rec["expected_minus_staged"] = sorted(expected - set(pairs))[:10]
    rec["status_letters"] = {s: list(pairs.values()).count(s) for s in set(pairs.values())}
    ok = (set(pairs) == expected and pairs.get(".gitignore") == "M"
          and all(v == "A" for p, v in pairs.items() if p != ".gitignore"))
    rec["staged_bytes_new"] = sum(os.path.getsize(p) for p in expected if p != ".gitignore")
    return finish("STAGED_OK" if ok else "REFUSED: staged set differs from selection", 0 if ok else 1)


if __name__ == "__main__":
    sys.exit(main())
