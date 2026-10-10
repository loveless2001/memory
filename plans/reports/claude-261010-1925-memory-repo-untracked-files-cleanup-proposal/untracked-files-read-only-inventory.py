"""Read-only inventory of untracked paths in the memory repo: size, owner, path references and sha256 bindings
from tracked files, byte-duplicates. Writes JSON to argv[2]. No file is modified."""
import collections, hashlib, json, os, subprocess, sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])


def sh(*a, **k):
    return subprocess.run(a, cwd=REPO, capture_output=True, text=True, **k).stdout


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


entries = [l[3:] for l in sh("git", "status", "--porcelain").splitlines()]
files = [f for f in sh("git", "ls-files", "--others", "--exclude-standard").splitlines()]
tracked = sh("git", "ls-files").splitlines()

fh = {}
for f in files:
    p = REPO / f
    if p.is_file() and not p.is_symlink():
        fh[f] = (sha(p), p.stat().st_size, p.stat().st_mtime)

# tracked file hashes (regular files only) for duplicate detection
th = {}
for f in tracked:
    p = REPO / f
    if p.is_file() and not p.is_symlink() and p.stat().st_size >= 4096:
        th[f] = sha(p)
tracked_hashes = set(th.values())

# which untracked-file sha256 values appear in tracked text (binding)
pat = Path(OUT).with_suffix(".patterns")
pat.write_text("\n".join(sorted({h for h, _s, _m in fh.values()})) + "\n")
bound = collections.defaultdict(set)
for line in sh("git", "grep", "-o", "-F", "-f", str(pat)).splitlines():
    src, _, h = line.partition(":")
    bound[h].add(src)

by_hash = collections.defaultdict(list)
for f, (h, s, m) in fh.items():
    by_hash[h].append(f)

rows = []
for e in entries:
    key = e.rstrip("/")
    mine = [f for f in fh if f == key or f.startswith(key + "/")]
    nbytes = sum(fh[f][1] for f in mine)
    refs = [r for r in sh("git", "grep", "-l", "-F", key).splitlines()]
    base = os.path.basename(key)
    base_refs = [r for r in sh("git", "grep", "-l", "-F", base).splitlines()] if len(base) >= 12 else []
    bound_files = {f: sorted(bound[fh[f][0]])[:5] for f in mine if fh[f][0] in bound}
    dup_elsewhere = [f for f in mine if len([g for g in by_hash[fh[f][0]] if not (g == key or g.startswith(key + "/"))]) > 0
                     or fh[f][0] in tracked_hashes]
    seal = [f for f in mine if os.path.basename(f).startswith("SHA256SUMS")]
    rows.append({
        "entry": e, "n_files": len(mine), "bytes": nbytes,
        "mtime_min": min((fh[f][2] for f in mine), default=None),
        "mtime_max": max((fh[f][2] for f in mine), default=None),
        "path_refs_in_tracked": refs[:8], "n_path_refs": len(refs),
        "basename_refs_in_tracked": base_refs[:8], "n_basename_refs": len(base_refs),
        "n_hash_bound_files": len(bound_files), "hash_bound_bytes": sum(fh[f][1] for f in bound_files),
        "hash_bound_examples": dict(list(bound_files.items())[:3]),
        "n_dup_files": len(dup_elsewhere), "dup_bytes": sum(fh[f][1] for f in dup_elsewhere),
        "seals": seal,
        "big_files": sorted(([f, fh[f][1]] for f in mine if fh[f][1] >= 5_000_000), key=lambda x: -x[1])[:5],
    })
OUT.write_text(json.dumps({"n_entries": len(entries), "n_files": len(files), "rows": rows}, indent=1))
print(len(entries), len(files), sum(r["bytes"] for r in rows))
