"""Frozen gate, matched errors and source-clustered descriptive comparisons."""
import json,runpy,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
ARMS=['current_direct','current_decision','trained_direct','trained_decision']
def summarize():
 verification,renders=runpy.run_path(str(HERE/'verify_artifacts.py'))['verify']();assert verification['complete']
 assert renders==read(HERE/'rendered-decisions.json')
 review=read(HERE/'review.json');assert review==runpy.run_path(str(HERE/'record_review.py'))['materialize']()
 cases=read(HERE/'preflight/eval-cases.json');cm={c['id']:c for c in cases};am={(j['arm'],j['id']):j for j in review['answers']}
 protected=read(HERE/'preflight/prior-passes.json')['required_ids'];cfg=read(HERE/'preflight/runtime-config.json')
 def score(ids,arm):
  js=[am[arm,cid] for cid in ids];structured=arm.endswith('decision')
  return {'total':len(js),'strict_correct':sum(j['verdict']=='pass' for j in js),'rendered_strict_correct':sum(j['rendered_verdict']=='pass' for j in js),
   'required_answer_correct':sum(j['task_complete'] for j in js),'strict_failures':[j['id'] for j in js if j['verdict']=='fail'],
   'rendered_strict_failures':[j['id'] for j in js if j['rendered_verdict']=='fail'],'required_answer_failures':[j['id'] for j in js if not j['task_complete']],
   'schema_valid':sum(j['schema_valid'] for j in js) if structured else None,'record_semantically_correct':sum(j['record_semantically_correct'] for j in js) if structured else None,
   'record_criteria_passes':{k:sum(j['record_criteria'][k] for j in js) for k in js[0]['record_criteria']} if structured and js else None}
 groups={'all':[c['id'] for c in cases],'protected_regression':protected}
 for split in ('test','regression'):
  ss=[c for c in cases if c['split']==split];groups[split]=[c['id'] for c in ss]
  for field in ('kind','question_form','scope'):
   for value in sorted({c[field] for c in ss}):groups[split+':'+field+':'+value]=[c['id'] for c in ss if c[field]==value]
 for relation in ('fact','preference','enjoyment'):
  groups['test:relation:'+relation]=[c['id'] for c in cases if c['split']=='test' and c['reference']['decision']['relation']==relation]
 scores={name:{a:score(ids,a) for a in ARMS} for name,ids in groups.items()}
 literal={}
 rm={(r['arm'],r['id']):r for r in renders}
 for arm in ('current_decision','trained_decision'):
  new_cases=[c for c in cases if c['split']=='test'];fields=list(new_cases[0]['reference']['decision'])
  literal[arm]={'total':160,'exact_full_record':0,'exact_semantic_fields':0,'fields':dict.fromkeys(fields,0)}
  for c in new_cases:
   p=rm[arm,c['id']]['parsed'];gold=c['reference']['decision']
   if not p['valid']:continue
   rec=p['record'];literal[arm]['exact_full_record']+=rec==gold
   literal[arm]['exact_semantic_fields']+=all(rec[k]==gold[k] for k in fields if k not in ('turn','quote'))
   for k in fields:literal[arm]['fields'][k]+=rec[k]==gold[k]
 transitions={}
 for before,after in [('current_direct','current_decision'),('current_direct','trained_direct'),('current_direct','trained_decision'),('current_decision','trained_decision'),('trained_direct','trained_decision')]:
  pair=before+'->'+after;transitions[pair]={}
  for split in ('test','regression'):
   ids=groups[split];transitions[pair][split]={}
   for metric in ('strict','rendered','required'):
    ok=lambda j:j['verdict']=='pass' if metric=='strict' else j['rendered_verdict']=='pass' if metric=='rendered' else j['task_complete']
    transitions[pair][split][metric]={'corrected':[cid for cid in ids if not ok(am[before,cid]) and ok(am[after,cid])],
     'regressed':[cid for cid in ids if ok(am[before,cid]) and not ok(am[after,cid])]}
 ts=scores['test'];candidate=ts['trained_decision'];losses=scores['protected_regression']['trained_decision']['strict_failures']
 gates={'new_strict_at_least_152':candidate['strict_correct']>=152,'beats_current_direct':candidate['strict_correct']>ts['current_direct']['strict_correct'],
  'beats_trained_direct':candidate['strict_correct']>ts['trained_direct']['strict_correct'],'zero_protected_regression_losses':not losses,
  'numerical_training_and_artifact_verification':verification['status']=='PASS' and verification['passed_cache_checks']==80}
 assert cfg['success_rule']['new_strict_minimum']==152 and cfg['success_rule']['new_total']==160
 new=[c for c in cases if c['split']=='test'];histories={json.dumps(c['history'],sort_keys=True):[] for c in new}
 for c in new:histories[json.dumps(c['history'],sort_keys=True)].append(c['id'])
 assert len(histories)==40 and all(len(ids)==4 for ids in histories.values())
 consistency={a:sum(all(am[a,cid]['verdict']=='pass' for cid in ids) for ids in histories.values()) for a in ARMS}
 intervals={}
 for baseline in ('current_direct','current_decision','trained_direct'):
  diffs=[sum(int(am['trained_decision',cid]['verdict']=='pass')-int(am[baseline,cid]['verdict']=='pass') for cid in ids)/len(ids) for ids in histories.values()]
  rng=random.Random(4109);boots=sorted(sum(rng.choice(diffs) for _ in diffs)/len(diffs) for _ in range(5000))
  intervals[baseline]={'mean_accuracy_difference':sum(diffs)/len(diffs),'descriptive_95pct_percentile_interval':[boots[124],boots[4874]],'resamples':5000,'clusters':40,'seed':4109}
 return {'status':'complete','verdict':'PASS' if all(gates.values()) else 'FAIL','independent_review':False,'predeclared_gates':gates,
  'protected_regression_loss_ids':losses,'protected_regression_total':len(protected),'scores':scores,'matched_transitions':transitions,
  'new_literal_record_agreement':literal,'new_histories_all_four_strict_correct':consistency,'new_history_clustered_differences':intervals,
  'interval_caveat':'Descriptive bootstrap over forty synthetic histories. It is not a random external sample, not independent question-level inference, and intervals do not modify the frozen pilot gate.',
  'verification':verification,'training':read(HERE/'run/training.json'),'clean_suite_gates':{a:{split:scores[split][a]['strict_correct']==scores[split][a]['total'] for split in ('test','regression')} for a in ARMS}}
if __name__=='__main__':
 r=summarize()
 if (HERE/'result-manifest.json').exists():assert r==read(HERE/'summary.json')
 else:(HERE/'summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'verdict':r['verdict'],'gates':r['predeclared_gates'],'new_scores':r['scores']['test'],'protected_losses':r['protected_regression_loss_ids']},indent=2))
