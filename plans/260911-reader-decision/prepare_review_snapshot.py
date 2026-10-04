"""Verify a read-only capture snapshot after both fixed trainings finish.

Final verification must prove the complete snapshot is an unchanged prefix of
final artifacts. This permits review during the last inference stage only.
"""
import json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=HERE/'preflight';S=HERE/'review-snapshot'
sys.path.insert(0,str(ROOT))
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.reader_decision_protocol import parse_decision,render_decision
from transformers import AutoTokenizer
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (S/'verification.json').exists(),'Preserve the single review snapshot'
 tr=read(S/'training.json');assert set(tr)=={'trained_direct','trained_decision'}
 assert all(t['optimizer_steps']==64 and t['examples_seen']==1024 for t in tr.values())
 cfg=read(P/'runtime-config.json');inp=read(P/'eval-inputs.json');caps=read(S/'captures.json');cases={c['id']:c for c in read(P/'eval-cases.json')}
 assert 1260<=len(caps)<1680
 for n,h in read(P/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
 expected=[]
 for i,r in enumerate(inp):
  arms=['current_direct','current_decision'];arms=arms[i%2:]+arms[:i%2];expected.extend((a,r) for a in arms)
 for a in ('trained_direct','trained_decision'):expected.extend((a,r) for r in inp)
 tok=AutoTokenizer.from_pretrained(cfg['model_id'],revision=cfg['model_revision'],local_files_only=True);renders=[]
 for c,(a,r) in zip(caps,expected):
  fmt='decision' if a.endswith('decision') else 'prose';assert c['id']==r['id'] and c['arm']==a and c['format']==fmt and c['messages']==r[fmt]['messages']
  assert c['input_tokens']==len(answer_prefix_ids(tok,c['messages'])) and c['output_cap']==cfg['output_cap_by_format'][fmt]
  for k,v in strict_body_capture(tok,c['token_ids'],tok.eos_token_id).items():assert c[k]==v
  assert c['adapter_sha256']==(cfg['prior_adapter_files']['adapter_model.safetensors'] if a.startswith('current') else tr[a]['adapter_sha256'])
  if fmt=='decision':
   case=cases[c['id']];parsed=parse_decision(c['text'],case['history'],case['query'])
   if not c['ended_at_eos'] or not c['body_structurally_valid']:parsed={'valid':False,'record':None,'error':'invalid or incomplete model body'}
   renders.append({'arm':a,'id':c['id'],'parsed':parsed,'rendered_text':render_decision(parsed)})
 (S/'rendered-decisions.json').write_text(json.dumps(renders,ensure_ascii=False,indent=2)+'\n')
 result={'status':'PASS','observed_at':datetime.now(timezone.utc).isoformat(),'both_fixed_trainings_complete':True,'captures':len(caps),
 'files':{n:sha(S/n) for n in ('captures.json','training.json','rendered-decisions.json')},
 'scope':'Source prompts, decoding, adapter identity and both training completions checked. Final verification additionally requires exact prefix and training equality with final hash-verified remote artifacts.'}
 (S/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
