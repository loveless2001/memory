"""Read-only dry run of r2 U1-U4 together: allowlisted files to commit vs codex's 407 exact ignore rules.
Uses `git check-ignore --no-index` with a temporary excludes file; stages, ignores and deletes nothing."""
import json, os, subprocess, sys, tempfile

R1 = "plans/reports/claude-261010-1925-memory-repo-untracked-files-cleanup-proposal"
C = "plans/reports/codex-261010-gravity-22715-untracked-proposal-audit"


def ignored(paths, rules):
    r = subprocess.run(["git", "-c", f"core.excludesFile={rules}", "check-ignore", "--no-index", "--stdin"],
                       input="\n".join(paths) + "\n", capture_output=True, text=True)
    return set(r.stdout.splitlines())


def main():
    with tempfile.NamedTemporaryFile("w", suffix=".rules", delete=False) as f:
        for name in ("u3-proposed-exact-ignore-rules.txt", "u4-proposed-exact-ignore-rules.txt"):
            f.write(open(f"{C}/{name}").read())
        rules = f.name
    commit = {r["path"] for n in ("u1-claude-files.json", "u2-run-text-files-to-commit.json")
              for r in json.load(open(f"{R1}/{n}"))}
    commit |= {r["path"] for r in json.load(open(f"{C}/u4-top-level-text-records-to-commit.json"))}
    commit |= {os.path.join(C, f) for f in os.listdir(C)}
    now = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                         capture_output=True, text=True).stdout.splitlines()
    own = os.path.dirname(os.path.abspath(__file__))
    now = [p for p in now if not os.path.abspath(p).startswith(own + os.sep)]   # this r2 dir is committed itself
    ig = ignored(now, rules)
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.splitlines()
    u3 = [r["path"] for r in json.load(open(f"{R1}/u3-run-binaries-local-only.json"))]
    bad_json = []
    for p in commit:
        if p.endswith(".json"):
            try:
                json.loads(open(p).read(), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
            except ValueError:
                bad_json.append(p)
    os.unlink(rules)
    out = {"untracked_now": len(now), "to_commit": len(commit), "to_commit_missing": sorted(commit - set(now))[:5],
           "to_commit_bytes": sum(os.path.getsize(p) for p in commit),
           "would_stay_visible": sorted(p for p in now if p not in commit and p not in ig)[:10],
           "to_commit_inside_ignored_roots_need_add_f": len(commit & ig),
           "u3_ignored": sum(p in ig for p in u3), "u3_total": len(u3),
           "tracked_matched_by_rules": sorted(ignored(tracked, rules))[:10],
           "strict_json_failures": sorted(bad_json)[:10]}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
