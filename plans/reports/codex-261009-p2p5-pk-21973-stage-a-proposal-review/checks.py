"""Read-only proposal/code/evidence checks plus a tiny CPU algebra counterexample.
No pretrained model, episode evaluation, optimizer or remote work.
"""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import torch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from memsub.sgm.address_supervision import address_pair_loss
from memsub.sgm.synthetic_pilot import PilotConfig

proposal = ROOT / 'plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/proposal.md'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(proposal) == '37cf82ebfe7855e92e56c32f7450e05d142e3c137b99e4e96d384fce74df217e'
assert proposal.read_bytes() == subprocess.check_output(['git', 'show', '41ffbd2:' + str(proposal.relative_to(ROOT))], cwd=ROOT)
(OUT / 'proposal-at-41ffbd2.md').write_bytes(proposal.read_bytes())

# Actual auxiliary loss can be zero for a constant address map, irrespective
# of the distinct q/k inputs. This is not a simulated retrieval result.
mlp = torch.nn.Linear(3, 2)
with torch.no_grad():
    mlp.weight.zero_()
    mlp.bias.zero_()
runtime = SimpleNamespace(cfg=SimpleNamespace(address_scale=8., selected_layers=(6,)),
                          adapters={'6': SimpleNamespace(address_mlp=mlp)})
q = [torch.tensor([[[1., 0., 0.], [0., 1., 0.]]]),
     torch.tensor([[[0., 0., 1.], [-1., 0., 0.]]])]
k = [torch.tensor([[[0., -1., 0.], [0., 0., -1.]]]),
     torch.tensor([[[1., 1., 0.], [0., 1., 1.]]])]
source = [{'write_k': {6: x}} for x in k]
queries = [{'read_q': {6: [x]}} for x in q]
aux = float(address_pair_loss(runtime, source, queries, torch.tensor([[0, 1]])).detach())
assert aux == 0.0
label = PilotConfig(backbone='qwen3-0.6b-base', aux_address_lambda=.1).result_label()
assert 'DIAGNOSTIC' not in label

base = ROOT / 'plans/reports/claude-261008-2350-p2p5-taskhead-dead-start-address-diagnosis'
index = json.loads((base / 'inputs-index.json').read_text())
early = {}
paths = [proposal, ROOT / 'memsub/sgm/address_supervision.py', ROOT / 'memsub/sgm/synthetic_pilot.py',
         ROOT / 'memsub/sgm/synthetic_pilot_evaluation.py', ROOT / 'memsub/sgm/synthetic_pilot_run.py',
         ROOT / 'scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py',
         ROOT / 'scripts/sgm-p2p5-local-gpu-timing-profile.py']
for name in ['qwen-probe-taskhead-s0-init', 'toy-p2c-curriculum-taskhead-s0-init', 'toy-p2c-curriculum-taskhead-s1-init']:
    e = next(e for e in index['entries'] if e['name'] == name)
    paths += [ROOT / e['manifest'], ROOT / e['telemetry']]
    rows = [json.loads(line) for line in (ROOT / e['telemetry']).read_text().splitlines() if line.strip()]
    early[name] = {'config': json.loads((ROOT / e['manifest']).read_text())['pilot_config'],
                   'dev_rows': [r for r in rows if 'eval' in r and r.get('step') in [0, 100, 500, 900, 1000, 1100, 1500]]}
profile = ROOT / 'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-l40s-profile-v2/volume-evidence/p2p5-l40s-profile-v2/profile-l40s/profile.json'
paths.append(profile)
p = json.loads(profile.read_text())
result = {'reviewed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'proposal_commit': '41ffbd2', 'constant_address_map_aux_loss': aux,
          'constant_map_counterexample_scope': 'auxiliary objective only; no retrieval or capability conclusion',
          'pretrained_aux_default_label': label,
          'one_occupied_head_of_sixteen_absent_mean': 15 / 16,
          'early_saved_evidence': early,
          'l40s_profile': {'source_sha256': p['memsub_source_sha256'], 'environment': p['environment'],
                          'phase1': p['configs'][0], 'readout_from_profile_script': 'residual_head'},
          'sources_sha256': {str(path.relative_to(ROOT)): sha(path) for path in paths},
          'new_training_updates': 0, 'model_forward': False, 'modal_calls': 0,
          'public_sources_checked': ['https://modal.com/pricing', 'https://modal.com/docs/guide/timeouts',
                                     'https://modal.com/docs/guide/apps', 'https://modal.com/docs/guide/functions']}
(OUT / 'evidence.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'proposal_matches_commit': True, 'constant_map_aux_loss': aux,
                  'pretrained_aux_default_label': label, 'new_training_updates': 0, 'modal_calls': 0}))
