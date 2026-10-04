"""Print complete source/answer packets for manual post-training semantic review."""
import argparse,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda n:json.loads((HERE/n).read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--split',choices=['test','regression'],required=True);p.add_argument('--start',type=int,default=0);p.add_argument('--count',type=int,default=16);p.add_argument('--run-dir',type=Path,default=HERE/'run');p.add_argument('--renders',type=Path,default=HERE/'rendered-decisions.json');p.add_argument('--arms',nargs='+',default=['current_direct','current_decision','trained_direct','trained_decision']);args=p.parse_args()
 training=json.loads((args.run_dir/'training.json').read_text())
 assert len(training)==2 and all(t['optimizer_steps']==64 for t in training.values()),'Do not open semantic review before both fixed trainings complete'
 cases=[c for c in read('preflight/eval-cases.json') if c['split']==args.split][args.start:args.start+args.count]
 caps={(c['arm'],c['id']):c for c in json.loads((args.run_dir/'captures.json').read_text())};renders={(c['arm'],c['id']):c for c in json.loads(args.renders.read_text())};seen=set()
 for c in cases:
  h=json.dumps(c['history'],ensure_ascii=False)
  if h not in seen:
   seen.add(h);print('\nSOURCE',c['family'],c['kind'])
   for i,m in enumerate(c['history']):print(f" T{i} {m['role']}: {m['content']}")
  print('\n',c['id'],c['query']);print(' REFERENCE',c['reference']['answer']);print(' REFERENCE CONDITIONS',json.dumps({k:v for k,v in c['reference'].items() if k not in ('answer','decision')},ensure_ascii=False))
  if 'decision' in c['reference']:print(' REFERENCE RECORD',json.dumps(c['reference']['decision'],ensure_ascii=False))
  for a in args.arms:
   if a=='current_direct' and args.split=='regression':continue
   x=caps[a,c['id']];print(' ',a,'BODY_VALID',x['body_structurally_valid'])
   if not a.endswith('decision'):print('  ANSWER',x['text'])
   else:
    r=renders[a,c['id']];rec=r['parsed']['record']
    if rec is None:print('  INVALID',r['parsed']['error'],'RAW',x['text'])
    else:print('  RECORD',rec['scope'],rec['relation'],rec['status'],repr(rec['value']),'|',rec['operation'],repr(rec['candidate']),'=>',rec['decision'],'| SOURCE',rec['turn'],repr(rec['quote']))
    print('  RENDER',r['rendered_text'])
 print('\nPACKET',args.split,args.start,args.start+len(cases),'CASES',len(cases))
if __name__=='__main__':main()
