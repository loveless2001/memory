"""Resolve existing checksum lists using their repository/snapshot context; no resealing."""
from pathlib import Path
import collections
import hashlib
import json
import re

REPO = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
catalog = json.loads((OUT / 'u4-audit-file-catalog.json').read_text())
files = {x['path']: x for c in catalog for x in c['contents']}
by_hash = collections.defaultdict(list)
for rel, x in files.items():
    by_hash[x['sha256']].append(rel)
resolved = []
unresolved = []
for entry in catalog:
    root = REPO / entry['root']
    for rel in entry['seals']:
        seal = REPO / rel
        records = []
        parents = [seal.parent, root, REPO]
        p = seal.parent
        while p.is_relative_to(root) and p != root:
            p = p.parent
            parents.append(p)
        for number, line in enumerate(seal.read_text().splitlines(), 1):
            if not line.strip() or line.startswith('#'):
                continue
            metadata = re.match(r'^memsub_source_sha256\s+([0-9a-fA-F]{64})$', line)
            if metadata:
                records.append({'line': number, 'status': 'source fingerprint metadata; not a file checksum',
                                'source_sha256': metadata.group(1), 'fingerprint_recomputed': False})
                continue
            match = re.match(r'^([0-9a-fA-F]{64})\s+[* ]?(.+)$', line)
            if not match:
                records.append({'line': number, 'status': 'unsupported checksum-line format'})
                continue
            want, target = match.groups()
            target = target.strip()
            candidates = [Path(target)] if Path(target).is_absolute() else [base / target for base in parents]
            direct = []
            changed = []
            for path in dict.fromkeys(candidates):
                if not path.is_file() or path.is_symlink():
                    continue
                relative = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else None
                actual = files[relative]['sha256'] if relative in files else hashlib.sha256(path.read_bytes()).hexdigest()
                if actual == want:
                    direct.append(str(path))
                else:
                    changed.append({'path': str(path), 'actual': actual})
            copies = [p for p in by_hash[want] if p.endswith('/' + target) or Path(p).name == Path(target).name]
            if direct:
                status = 'verified at existing repository/snapshot path'
            elif copies:
                status = 'expected bytes retained in named audit copy; original path context unavailable or changed'
            else:
                status = 'unresolved historical dependency or checksum mismatch'
            row = {'seal': rel, 'line': number, 'target': target, 'expected_sha256': want, 'status': status,
                   'matching_paths': direct, 'named_retained_copies': copies[:5], 'existing_nonmatching_paths': changed}
            records.append(row)
            if status.startswith('unresolved'):
                unresolved.append(row)
        resolved.append({'seal': rel, 'records': records})
(OUT / 'u4-contextual-seal-records.json').write_text(json.dumps(resolved, indent=1))
(OUT / 'u4-unresolved-historical-seal-records.json').write_text(json.dumps(unresolved, indent=2))
summary = {'manifests': len(resolved), 'record_outcomes': dict(collections.Counter(x['status'] for s in resolved for x in s['records'])),
           'unresolved_record_count': len(unresolved), 'no_old_manifest_or_content_rewritten': True}
(OUT / 'u4-contextual-seal-summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
