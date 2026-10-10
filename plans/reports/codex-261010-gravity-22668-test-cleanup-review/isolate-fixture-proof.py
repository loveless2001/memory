"""Build a private current-source fixture; preserve all production artifacts."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile

REPO = Path('/home/lenovo/projects/memory')
OUT = Path(__file__).resolve().parent
TREE = OUT / 'fixture-tree'
COMMIT = '244718ec83074b7f18d8a7c277d2d35f2a169f39'
manifest_rel = 'configs/m4_sgm_p2p5_campaign_analysis_manifest.json'
manifest_blob = subprocess.check_output(['git', 'show', COMMIT + ':' + manifest_rel], cwd=REPO)
manifest = json.loads(manifest_blob)
tests = ['test_sgm_pk_campaign_readings_orchestration_fast.py', 'test_sgm_pk_campaign_readings_runner.py',
         'test_sgm_pk_control_plane_reaper_and_manifest_label.py', 'test_sgm_pk_posthoc_validation_amendment.py']
paths = ['memsub', 'scripts', 'modal-runners', 'configs', *['tests/' + x for x in tests]]
paths += [p for section in ['analysis', 'launch'] for p in manifest[section] if p.startswith('plans/')]
TREE.mkdir(exist_ok=True)
data = subprocess.check_output(['git', 'archive', COMMIT, *sorted(set(paths))], cwd=REPO)
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    archive.extractall(TREE, filter='data')

# Bind ONLY the private manifest to its current copied source. No historical manifest changes.
code = "from pathlib import Path;from memsub.sgm.synthetic_pilot_run import source_tree_sha256;print(source_tree_sha256(Path('memsub')))"
sha = subprocess.check_output([str(REPO / '.venv/bin/python'), '-c', code], cwd=TREE, text=True).strip()
assert sha == 'd86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532'
manifest['memsub_source_sha256'] = sha
(TREE / manifest_rel).write_text(json.dumps(manifest, indent=2) + '\n')

# The schema mutation test needs telemetry, not the unavailable terminal checkpoint.
posthoc = TREE / 'tests/test_sgm_pk_posthoc_validation_amendment.py'
original = posthoc.read_text()
needle = '    out = private_slot(tmp_path) / "cells/learned-n32-s1/epoch-1/attempt-1/out"\n'
replacement = ('    out = tmp_path / "schema-out"\n'
               '    shutil.copytree(EVID / "learned-n32/volume-evidence/collect-1/learned-n32/cells/learned-n32-s1/epoch-1/attempt-1/out", out)\n')
assert original.count(needle) == 1
posthoc.write_text(original.replace(needle, replacement))
(OUT / 'fixture-posthoc.patch').write_text(subprocess.run(['diff', '-u', str(REPO / 'tests/test_sgm_pk_posthoc_validation_amendment.py'), str(posthoc)], capture_output=True, text=True).stdout)
(OUT / 'fixture-metadata.json').write_text(json.dumps({'source_commit': COMMIT, 'fixture_source_sha256': sha,
    'production_manifest_sha256': hashlib.sha256((REPO / manifest_rel).read_bytes()).hexdigest(),
    'original_manifest_sha256_at_commit': hashlib.sha256(manifest_blob).hexdigest(),
    'only_fixture_changes': ['private manifest source fingerprint', 'private schema-test out-only copy'],
    'production_files_modified': [], 'real_evidence_read_only_root': str(REPO)}, indent=2))
print(str(TREE))
