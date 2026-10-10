"""Independent saved-package and offline image-import audit; no build, RPC, or model forward."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PLAN = ROOT / 'plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe'
IMPL = PLAN / 'implementation'
sys.path.insert(0, str(ROOT))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p, name):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


hashes = {}
for line in (IMPL / 'SHA256SUMS-implementation-package.txt').read_text().splitlines():
    h, rel = line.split(maxsplit=1)
    rel = rel.lstrip('*')
    hashes[rel] = {'expected': h, 'actual': sha(ROOT / rel)}
assert len(hashes) == 24 and all(x['actual'] == x['expected'] for x in hashes.values())
freeze = load(ROOT / 'scripts/sgm-p2p5-readout-probe-registry-and-schema-freeze.py', 'audit_freeze')
reg, schema = freeze.derive()
assert reg == json.loads(freeze.REGISTRY_OUT.read_text())
assert schema == json.loads(freeze.SCHEMA_OUT.read_text())

mutations = json.loads((IMPL / 'mutation-checks-readout-probe.json').read_text())
entries = {k:v for k,v in mutations.items() if isinstance(v, dict) and 'aimed_test' in v}
assert len(entries) == 26 and mutations['baseline']['ok'] and mutations['all_ok']
assert all(v['rc'] != 0 and v['aimed_test'] in v['failed'] and v['ok'] for v in entries.values())

ledger = json.loads((PLAN / 'probe-priced-ledger.json').read_text())
deadline = D(str(ledger['deadline_s']))
rate = D('.000694') + D(2) * (D(8)*D('.0000131') + D(64)*D('.00000222'))
gpu = (deadline + D(240))*rate
reaper = (D(1800)+deadline+D(240))/D(120)*D(140)*D(2)*(D('.125')*D('.0000131')+D('.25')*D('.00000222'))
total = gpu + reaper + D(2)*D('.168384') + D(2)
assert deadline == D('31946.2') and rate == D(str(ledger['rate_usd_s']['value']))
assert total <= D('40.75') and D(str(ledger['cap_request_usd'])) == D('40.75')

import modal
from modal.cli.import_refs import ImportRef, import_file_or_module
from modal._utils.async_utils import synchronizer
from modal._functions import _Function

runner_rel = 'modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py'
runner = import_file_or_module(ImportRef(str(ROOT / runner_rel), False))
seen, builders = set(), []


def walk(obj):
    obj = synchronizer._translate_in(obj)
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, _Function) and obj.info.function_name == '_build_environment':
        mounts = []
        for mount in obj.spec.mounts:
            for entry in (getattr(mount, '_entries', ()) or ()):
                mounts.append({'type': type(entry).__name__, 'local': str(getattr(entry, 'local_file', None)),
                               'remote': str(getattr(entry, 'remote_path', None))})
        builders.append({'serialized': obj.info.is_serialized(), 'module': obj.info.module_name,
                         'mounts': mounts, 'base_image_mount_layers': len(obj.spec.image._mount_layers)})
    for dep in obj.deps():
        walk(dep)


walk(runner.image)
assert len(builders) == 1 and builders[0]['serialized'] is False
assert not any('readout-probe-slot-logic' in x['remote'] for x in builders[0]['mounts'])
assert builders[0]['base_image_mount_layers'] == 0

logic = ROOT / runner.L.SLOT_LOGIC_FILE
results = {}
with tempfile.TemporaryDirectory(prefix='codex-21758-build-import-') as td:
    dest = Path(td)
    shutil.copyfile(ROOT / runner_rel, dest / Path(runner_rel).name)
    # The SDK's FILE definition imports the whole runner before calling the builder.
    code = ('import sys; from modal.cli.import_refs import ImportRef, import_file_or_module; '
            'm=import_file_or_module(ImportRef(sys.argv[1],False)); '
            'print("IMPORT_OK",m._build_environment.__name__)')
    for label, include in [('builder_mounts_only', False), ('sibling_added_control', True)]:
        if include:
            shutil.copyfile(logic, dest / logic.name)
        r = subprocess.run([sys.executable, '-c', code, str(dest / Path(runner_rel).name)],
                           cwd=ROOT, capture_output=True, text=True, timeout=30)
        results[label] = {'rc': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
assert results['builder_mounts_only']['rc'] != 0
assert 'FileNotFoundError' in results['builder_mounts_only']['stderr']
assert logic.name in results['builder_mounts_only']['stderr']
assert results['sibling_added_control']['rc'] == 0

from memsub.sgm.synthetic_pilot_run import source_tree_sha256
result = {'head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
          'hashes': hashes, 'package_files': len(hashes),
          'code_to_package_diff': subprocess.check_output(['git','diff','--name-status','fbfebe0','c3c6fa2'],cwd=ROOT,text=True),
          'memsub_sha256': source_tree_sha256(ROOT/'memsub'),
          'registry_schema_rederive_equal': True, 'saved_mutations_aimed_caught': len(entries),
          'ledger_decimal': {'gpu':str(gpu),'reaper':str(reaper),'total':str(total),'cap':'40.75'},
          'modal_version': modal.__version__, 'builder_specs': builders, 'import_reproduction': results}
(OUT/'package-and-import-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('hashes','import_reproduction')},indent=2))
