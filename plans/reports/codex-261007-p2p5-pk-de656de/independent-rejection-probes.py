"""CPU-only rejection probes on reviewer-owned copies; originals remain intact."""
import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

spec = module('audit_spec_v2', ROOT / 'tests/test_sgm_pk_packed_proof_acceptance_compare.py')
acc = spec.acc
es = spec.es
proof = HERE / 'pytest-tmp/proof0'
run = HERE / 'rejection-probes'
run.mkdir(exist_ok=False)
results = {'baseline': spec.evaluate(proof)}
assert results['baseline']['pass'], results['baseline']

def clone(name):
    out = run / name
    shutil.copytree(proof, out)
    return out

def outputs(ev):
    for scen, sc in spec.TINY['scenarios'].items():
        for cell in sc['cells']:
            _, rec = acc.authority(ev / scen / 'cells' / cell, [1, 2])
            if rec['state'] == es.COMPLETE:
                yield scen, cell, ev / scen / rec['outputs']['attempt'] / 'out'

ev = clone('joint-missing-metric-fields')
for scen, cell, out in outputs(ev):
    p = out / 'metrics.json'
    m = json.loads(p.read_text())
    m.pop('n_queries')
    for key, value in m['final'].items():
        if value is not None:
            m['final'][key] = {}
    p.write_text(json.dumps(m))
    spec._rebind(ev, scen, cell)
results['joint_missing_metric_fields'] = spec.evaluate(ev)

ev = clone('joint-missing-telemetry-fields')
for scen, cell, out in outputs(ev):
    p = out / 'routing_telemetry.jsonl'
    rows = [json.loads(line) for line in p.read_text().splitlines()]
    p.write_text(''.join(json.dumps({'eval': {}} if 'eval' in r else {'loss': 0.0}) + '\n' for r in rows))
    spec._rebind(ev, scen, cell)
results['joint_missing_telemetry_fields'] = spec.evaluate(ev)

ev = clone('wrong-predecessor-digests')
def zero_digests(rec):
    if rec.get('inherited_from'):
        rec['inherited_from']['record_sha256'] = '0' * 64
    if rec.get('predecessor_snapshot'):
        zero_digests(rec['predecessor_snapshot'])
for path in ev.rglob('state.json'):
    rec = json.loads(path.read_text())
    zero_digests(rec)
    es.write_record(path.parent.parent, rec)
results['wrong_predecessor_digests'] = spec.evaluate(ev)

# The real validator is invoked on the retained CPU timing smoke, with explicit
# smoke-cpu provenance. Only the reviewer-owned exit stub supplies commit values.
timing = ROOT / 'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-prep/timing-smoke-cpu-local-v2/timing.json'
t = json.loads(timing.read_text())
for name, empty in [('cpu-timing-as-gpu', False), ('timing-with-no-eval-checkpoint-workers', True)]:
    dest = run / name
    (dest / 'timing').mkdir(parents=True)
    d = copy.deepcopy(t)
    if empty:
        for config in d['configs']:
            config['eval_and_checkpoint'] = []
    (dest / 'timing/timing.json').write_text(json.dumps(d))
    (dest / 'timing.exit.json').write_text(json.dumps({'child_exit': 0, 'commit_s': [0.1, 0.1, 0.1]}))
    try:
        results[name] = {'accepted': True, 'validation': acc.validate_timing(dest, spec.TINY['timing']),
                         'actual_report_gpu': d.get('gpu'), 'synthetic_exit_stub': True}
    except acc.Fail as e:
        results[name] = {'accepted': False, 'failure': str(e)}

# Confirm that the real supervisor uses the same incomplete semantic validator.
ev = run / 'joint-missing-metric-fields'
cell = 'learned-n4-s99'
_, original = acc.authority(ev / 'A/cells' / cell, [1, 2])
sup = spec.SlotSupervisor(root=ev / 'A', cells={cell: spec.CELLS[cell]}, epoch=1, admitted=[1], identity=spec.ID,
                         checkpoint_every=2, eval_cfg=spec.TINY['eval'], commit=lambda: None, reload=lambda: None,
                         registry=spec.REG['by_arm']['learned'])
sup.records[cell] = copy.deepcopy(original)
sup.records[cell]['state'] = es.TRAINED
sup.records[cell].pop('outputs')
sup.finish(cell, 0)
results['incomplete_metrics_supervisor_state'] = sup.records[cell]['state']

results['scope'] = 'CPU_ONLY_REJECTION_PROBES_ON_NEW_SCRATCH_COPIES_NO_GPU_LAUNCH'
with (HERE / 'independent-rejection-probes.json').open('x') as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
