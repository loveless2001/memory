"""Read-only proposal audit; mutations are limited to this new review folder."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

REPO = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
PROPOSAL = REPO / 'plans/reports/claude-261010-1925-memory-repo-untracked-files-cleanup-proposal'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


checks = {}
seal = subprocess.run(['sha256sum', '-c', '--quiet', 'SHA256SUMS'], cwd=PROPOSAL, capture_output=True, text=True)
checks['proposal seal valid'] = seal.returncode == 0
lists = {}
validation = {}
invalid_json = []
secret_hits = []
patterns = {
    'HF token pattern': re.compile(r'\bhf_[A-Za-z0-9]{20,}\b'),
    'GitHub token pattern': re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b'),
    'API token pattern': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),
    'AWS key pattern': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private key marker': re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
}
all_paths = set()
for selected, name in [('U1', 'u1-claude-files.json'), ('U2', 'u2-run-text-files-to-commit.json'), ('U3', 'u3-run-binaries-local-only.json')]:
    items = json.loads((PROPOSAL / name).read_text())
    lists[selected] = items
    details = []
    for item in items:
        rel = item['path']
        p = REPO / rel
        assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
        assert rel not in all_paths
        all_paths.add(rel)
        st = p.lstat()
        actual = digest(p) if stat.S_ISREG(st.st_mode) else None
        details.append({'path': rel, 'regular': stat.S_ISREG(st.st_mode), 'bytes': st.st_size,
                        'sha256': actual, 'matches': actual == item['sha256'] and st.st_size == item['bytes']})
        if selected != 'U3':
            txt = p.read_text()
            for kind, pattern in patterns.items():
                if pattern.search(txt):
                    secret_hits.append({'path': rel, 'pattern': kind})  # Never include token contents.
            if p.suffix == '.json':
                try:
                    json.loads(txt, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                except ValueError as ex:
                    invalid_json.append({'path': rel, 'sha256': actual, 'error_class': type(ex).__name__})
            elif p.suffix == '.jsonl':
                for line_number, line in enumerate(txt.splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                    except ValueError as ex:
                        invalid_json.append({'path': rel, 'sha256': actual, 'line': line_number, 'error_class': type(ex).__name__})
                        break
    validation[selected] = {'count': len(items), 'bytes': sum(d['bytes'] for d in details),
                            'all_match': all(d['matches'] for d in details), 'files': details}
    checks[selected + ' fixed allowlist hashes match'] = validation[selected]['all_match']

inventory = json.loads((PROPOSAL / 'untracked-inventory.json').read_text())
rows = inventory['rows']
audit_rows = [r for r in rows if r['entry'].startswith('plans/reports/codex-')]
run_rows = [r for r in rows if not r['entry'].startswith('plans/reports/')]
roots = [r['entry'].rstrip('/') for r in audit_rows]
catalog = []
links = []
for rel in roots:
    root = REPO / rel
    st = root.lstat()
    kind = 'directory' if stat.S_ISDIR(st.st_mode) else 'regular' if stat.S_ISREG(st.st_mode) else 'symlink' if stat.S_ISLNK(st.st_mode) else 'other'
    count, size, extension_counts, seals = 0, 0, collections.Counter(), []
    root_files = []
    walk = os.walk(root, followlinks=False) if kind == 'directory' else [(root.parent, [], [root.name])]
    for parent, dirs, names in walk:
        for name in dirs + names:
            p = Path(parent) / name
            st = p.lstat()
            relative = str(p.relative_to(REPO))
            if stat.S_ISLNK(st.st_mode):
                links.append({'path': relative, 'target': os.readlink(p)})
            elif stat.S_ISREG(st.st_mode):
                root_files.append({'path': relative, 'bytes': st.st_size, 'sha256': digest(p)})
                count += 1
                size += st.st_size
                extension_counts[p.suffix or '(none)'] += 1
                if p.name.startswith('SHA256SUMS'):
                    seals.append(relative)
    catalog.append({'root': rel, 'kind': kind, 'dev': root.lstat().st_dev, 'inode': root.lstat().st_ino,
                    'uid': root.lstat().st_uid, 'files': count, 'bytes': size,
                    'extension_counts': dict(extension_counts), 'seals': seals, 'contents': root_files})

# U1 blobs should already exist in Git; compare canonical blob IDs with index.
index = subprocess.check_output(['git', 'ls-files', '-s', '-z'], cwd=REPO).split(b'\0')
by_oid = collections.defaultdict(list)
for row in index:
    if not row:
        continue
    meta, path = row.split(b'\t', 1)
    by_oid[meta.split()[1].decode()].append(path.decode())
u1_duplicates = []
for item in lists['U1']:
    oid = subprocess.check_output(['git', 'hash-object', item['path']], cwd=REPO, text=True).strip()
    u1_duplicates.append({'path': item['path'], 'blob_oid': oid, 'tracked_identical_paths': by_oid[oid]})
checks['U1 already exists as tracked Git blobs'] = all(x['tracked_identical_paths'] for x in u1_duplicates)

# Capture root-scoped retention rules as a proposal only, not .gitignore mutations.
(OUT / 'u4-retain-local-exact-roots.json').write_text(json.dumps(roots, indent=2))
(OUT / 'u4-audit-file-catalog.json').write_text(json.dumps(catalog, indent=1))
(OUT / 'u4-audit-symlinks.json').write_text(json.dumps(links, indent=2))
result = {'checks': checks, 'allowlist_validation': validation, 'invalid_json_records': invalid_json,
          'secret_pattern_hits': secret_hits, 'U1_duplicates': u1_duplicates,
          'audit_roots': len(roots), 'audit_root_types': dict(collections.Counter(c['kind'] for c in catalog)),
          'audit_regular_files': sum(c['files'] for c in catalog),
          'audit_regular_bytes': sum(c['bytes'] for c in catalog), 'audit_symlinks': len(links),
          'run_entries': len(run_rows), 'run_entries_without_path_reference': sum(r['n_path_refs'] == 0 for r in run_rows),
          'run_entries_without_hash_bound_file': sum(r['n_hash_bound_files'] == 0 for r in run_rows),
          'disk_free_bytes': shutil.disk_usage(REPO).free, 'proposal_seal_stdout': seal.stdout,
          'proposal_seal_stderr': seal.stderr, 'production_mutations': 0}
(OUT / 'independent-results.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k: result[k] for k in ['checks', 'invalid_json_records', 'secret_pattern_hits', 'audit_roots',
     'audit_root_types', 'audit_regular_files', 'audit_regular_bytes', 'audit_symlinks', 'run_entries',
     'run_entries_without_path_reference', 'run_entries_without_hash_bound_file', 'disk_free_bytes']}))
