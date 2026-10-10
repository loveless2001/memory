"""Revision-3 independent CPU rejection probes; all edits use new scratch copies."""
import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sp = importlib.util.spec_from_file_location('audit_r3_tests', ROOT / 'tests/test_sgm_pk_packed_proof_acceptance_compare.py')
spec = importlib.util.module_from_spec(sp)
sp.loader.exec_module(spec)
acc, es = spec.acc, spec.es
proof = HERE / 'pytest-tmp/proof0'
run = HERE / 'rejection-probes'
run.mkdir(exist_ok=False)
results = {'baseline': spec.evaluate(proof)}
assert results['baseline']['pass'], results['baseline']

def clone(name):
    dest = run / name
    shutil.copytree(proof, dest)
    return dest

def complete(ev):
    return spec._complete_outs(ev)

# Previously reported complete semantic omissions must now fail.
ev = clone('prior-joint-metric-omission')
for scen, cell, out in complete(ev):
    p = out / 'metrics.json'
    m = json.loads(p.read_text())
    m.pop('n_queries')
    m['final'] = {k: (None if v is None else {}) for k, v in m['final'].items()}
    p.write_text(json.dumps(m)); spec._rebind(ev, scen, cell)
results['prior_joint_metric_omission'] = spec.evaluate(ev)

# Normalization must not collapse a missing entry for one layer into the
# corresponding entry still present for a different layer.
ev = clone('joint-one-layer-telemetry-omission')
for scen, cell, out in complete(ev):
    p = out / 'routing_telemetry.jsonl'
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    for row in rows:
        if 'loss' in row:
            row['grad_norm'].pop('L1/q_proj')
    p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    p = out / 'metrics.json'; m = json.loads(p.read_text())
    m['train_last']['grad_norm'].pop('L1/q_proj')
    p.write_text(json.dumps(m)); spec._rebind(ev, scen, cell)
results['joint_one_layer_telemetry_omission'] = spec.evaluate(ev)

# Retaining a row count is not full (intervention, batch, episode, query) coverage.
ev = clone('joint-duplicated-prediction-rows')
for scen, cell, out in complete(ev):
    p = out / 'per_example_results.jsonl'
    rows = p.read_text().splitlines()
    p.write_text((rows[0] + '\n') * len(rows))
    spec._rebind(ev, scen, cell)
results['joint_duplicated_prediction_rows'] = spec.evaluate(ev)

def supervisor_finish(ev, name):
    cell = 'learned-n4-s99'
    _, rec = acc.authority(ev / 'A/cells' / cell, [1, 2])
    sup = spec.SlotSupervisor(root=ev / 'A', cells={cell: spec.CELLS[cell]}, epoch=1, admitted=[1],
        identity=spec.ID, checkpoint_every=2, eval_cfg=spec.TINY['eval'], commit=lambda: None,
        reload=lambda: None, registry=spec.REG['by_arm']['learned'], schema=spec.SCHEMA['by_arm']['learned'])
    sup.records[cell] = copy.deepcopy(rec)
    sup.records[cell]['state'] = es.TRAINED
    sup.records[cell].pop('outputs')
    sup.finish(cell, 0)
    results[name] = sup.records[cell]['state']

supervisor_finish(run / 'joint-one-layer-telemetry-omission', 'layer_omission_supervisor_state')
supervisor_finish(run / 'joint-duplicated-prediction-rows', 'duplicated_rows_supervisor_state')

# JSON's overflow numeric literal bypasses parse_constant; it must still be
# rejected before durable COMPLETE publication, not merely during equivalence.
ev = clone('overflow-literal-in-metric')
out = next(o for s, c, o in complete(ev) if s == 'A' and c.endswith('s99'))
p = out / 'metrics.json'; m = json.loads(p.read_text())
m['final']['heldout_none']['accuracy'] = 'AUDIT_OVERFLOW_LITERAL'
p.write_text(json.dumps(m).replace('"AUDIT_OVERFLOW_LITERAL"', '1e999'))
spec._rebind(ev, 'A', 'learned-n4-s99')
results['overflow_literal_acceptance'] = spec.evaluate(ev)
supervisor_finish(ev, 'overflow_literal_supervisor_state')

ev = clone('prior-zeroed-predecessor-digest')
cdir = ev / 'B/cells/learned-n4-s99'; rec = es.read_record(cdir, 2)
rec['inherited_from']['record_sha256'] = '0' * 64
es.write_record(cdir, rec)
results['prior_zeroed_predecessor_digest'] = spec.evaluate(ev)

# Synthetic validator fixtures, explicitly not GPU/commit evidence.
def tprobe(name, mutate=None):
    dest = run / name
    d = spec._t(dest, mutate=mutate)
    try:
        results[name] = {'accepted': True, 'validation': acc.validate_timing(d, spec.GRID['timing'], spec.TEXP, gpu=True),
                         'SYNTHETIC_VALIDATOR_FIXTURE': True}
    except acc.Fail as e:
        results[name] = {'accepted': False, 'failure': str(e), 'SYNTHETIC_VALIDATOR_FIXTURE': True}

tprobe('timing-valid-synthetic-baseline')
tprobe('prior-empty-timing-measurements', lambda t: [c.__setitem__('eval_and_checkpoint', []) for c in t['configs']])
tprobe('timing-duplicate-rank', lambda t: t['configs'][0]['workers'][1].__setitem__('rank', 0))
tprobe('timing-wrong-k', lambda t: t['configs'][0]['workers'][0].__setitem__('k', 1))
tprobe('timing-duplicate-update-ids', lambda t: [u.__setitem__('update', 0) for u in t['configs'][0]['workers'][0]['updates']])
tprobe('timing-inconsistent-fixed-work-rate', lambda t: t['configs'][0].__setitem__('fixed_work_updates_per_s', 1e9))

# Independently recover the frozen schema from this real-worker run's outputs.
from memsub.sgm.packed_slot_cell_output_validation import output_schemas
out = next(o for s, c, o in complete(proof) if s == 'A' and c.endswith('s99'))
actual, layers = output_schemas(out, spec.CELLS['learned-n4-s99'])
results['frozen_schema_reconstruction'] = {'matches': actual == spec.SCHEMA['by_arm']['learned'],
                                         'tiny_layers_seen': sorted(layers)}
results['scope'] = 'CPU_ONLY_SCRATCH_COPIES_NO_GPU_DEPLOY_LAUNCH_STOP_COMMIT_PUSH'
with (HERE / 'independent-rejection-probes.json').open('x') as f: json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
