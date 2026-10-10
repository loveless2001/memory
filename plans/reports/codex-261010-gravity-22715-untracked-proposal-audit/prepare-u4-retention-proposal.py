"""Prepare an exact, non-destructive U4 proposal. No Git/staging/ignore changes."""
from pathlib import Path
import collections
import hashlib
import json
import re
import subprocess

REPO = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
catalog = json.loads((OUT / 'u4-audit-file-catalog.json').read_text())
checks = []
for entry in catalog:
    for rel in entry['seals']:
        seal = REPO / rel
        try:
            p = subprocess.run(['sha256sum', '-c', '--quiet', seal.name], cwd=seal.parent,
                               capture_output=True, text=True, timeout=20)
            checks.append({'seal': rel, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        except subprocess.TimeoutExpired:
            checks.append({'seal': rel, 'exit_code': None, 'timeout_seconds': 20})
(OUT / 'u4-existing-seal-validation.json').write_text(json.dumps(checks, indent=2))

text_types = {'.md', '.json', '.jsonl', '.txt', '.log', '.out', '.py', '.csv', '.tsv', '.yaml', '.yml', '.toml'}
patterns = {
    'HF token pattern': re.compile(r'\bhf_[A-Za-z0-9]{20,}\b'),
    'GitHub token pattern': re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b'),
    'API token pattern': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),
    'AWS key pattern': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private key marker': re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
}
packet, exclusions, secret_hits = [], [], []
for entry in catalog:
    for item in entry['contents']:
        relative = Path(item['path']).relative_to(entry['root']) if entry['kind'] == 'directory' else Path(item['path']).name
        if entry['kind'] == 'directory' and len(relative.parts) != 1:
            continue
        p = REPO / item['path']
        if p.suffix not in text_types and not p.name.startswith('SHA256SUMS'):
            continue
        try:
            text = p.read_text()
        except UnicodeError:
            exclusions.append({'path': item['path'], 'reason': 'not UTF-8 text; retained locally'})
            continue
        hits = [kind for kind, pattern in patterns.items() if pattern.search(text)]
        if hits:
            secret_hits.append({'path': item['path'], 'patterns': hits})
            exclusions.append({'path': item['path'], 'reason': 'token/private-key pattern; inspect before any commit'})
            continue
        if p.suffix in {'.json', '.jsonl'}:
            try:
                lines = text.splitlines() if p.suffix == '.jsonl' else [text]
                for line in lines:
                    if line.strip():
                        json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            except ValueError:
                exclusions.append({'path': item['path'], 'reason': 'non-strict JSON; retain raw locally and propose pinned sidecar/exemption separately'})
                continue
        assert hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256']
        packet.append(item)

(OUT / 'u4-top-level-text-records-to-commit.json').write_text(json.dumps(packet, indent=2))
(OUT / 'u4-local-only-text-exclusions.json').write_text(json.dumps(exclusions, indent=2))
(OUT / 'u4-records-secret-pattern-hits.json').write_text(json.dumps(secret_hits, indent=2))
# Exact roots only. There is no wildcard covering future audits and no actual ignore-file edit.
rules = []
for entry in catalog:
    path = entry['root'].replace('\\', '\\\\').replace(' ', '\\ ').replace('#', '\\#').replace('!', '\\!').replace('[', '\\[').replace('?', '\\?').replace('*', '\\*')
    rules.append('/' + path + ('/' if entry['kind'] == 'directory' else ''))
(OUT / 'u4-proposed-exact-ignore-rules.txt').write_text('\n'.join(rules) + '\n')
summary = {'catalog_snapshot_entries': len(catalog), 'entry_types': dict(collections.Counter(c['kind'] for c in catalog)),
           'sealed_manifest_files_checked': len(checks), 'seal_checks_passed': sum(x['exit_code'] == 0 for x in checks),
           'seal_checks_failed': sum(x['exit_code'] != 0 for x in checks), 'text_records_to_commit': len(packet),
           'text_record_bytes': sum(x['bytes'] for x in packet), 'local_text_exclusions': len(exclusions),
           'secret_pattern_hits_count': len(secret_hits), 'binary_and_nested_files_retained_locally': True,
           'deletions_proposed': 0, 'staging_or_ignore_mutations': 0,
           'new_review_folder_outside_original_snapshot': str(OUT.relative_to(REPO))}
(OUT / 'u4-proposal-summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
