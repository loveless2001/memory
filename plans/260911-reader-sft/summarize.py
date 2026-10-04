"""Validate evidence-bound judgments and the predeclared trainability rule."""
import hashlib,json
from pathlib import Path
from collections import Counter,defaultdict
HERE=Path(__file__).resolve().parent
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct','body_valid','within_90_words')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate_evidence(evidence,capture,history):
    kinds=set()
    for e in evidence:
        assert set(e)=={'where','index','quote'} and type(e['index']) is int and e['quote']
        rows={'answer':[{'content':capture['text']}],'history':history,'reader_message':capture['messages']}[e['where']]
        assert 0<=e['index']<len(rows) and e['quote'] in rows[e['index']]['content'];kinds.add(e['where'])
    assert {'answer','history','reader_message'}<=kinds

def summarize():
    artifact=read(HERE/'run/artifact-verification.json');assert artifact['complete'] and artifact['status']=='PASS'
    cases={c['id']:c for c in read(HERE/'preflight/eval-cases.json')};caps=read(HERE/'run/captures.json');review=read(HERE/'review.json')
    assert review['status']=='complete' and review['captures_sha256']==sha(HERE/'run/captures.json') and review['cases_sha256']==sha(HERE/'preflight/eval-cases.json')
    assert len(review['answers'])==len(caps)==288
    counts=defaultdict(lambda:defaultdict(Counter));kinds=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    forms=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)));criteria=defaultdict(lambda:defaultdict(Counter));index={}
    for c,j in zip(caps,review['answers']):
        assert (c['id'],c['arm'])==(j['id'],j['arm']) and j['reason']
        assert all(type(j[k]) is bool for k in FIELDS) and j['verdict']==('pass' if all(j[k] for k in FIELDS) else 'fail')
        assert j['body_valid']==c['body_structurally_valid'] and j['within_90_words']==c['within_90_words']
        case=cases[c['id']];validate_evidence(j['evidence'],c,case['history']);index[c['id'],c['arm']]=j
        for group in (case['split'],'all'):
            x=counts[group][c['arm']];x['n']+=1;x['strict_pass']+=j['verdict']=='pass';x['task_correct']+=j['task_complete']
        for table,dim in ((kinds,case['kind']),(forms,case['question_form'])):
            x=table[case['split']][dim][c['arm']];x['n']+=1;x['strict_pass']+=j['verdict']=='pass';x['task_correct']+=j['task_complete']
        for k in FIELDS:criteria[case['split']][c['arm']][k]+=j[k]
    effects={};known_losses=[];failures={a:[] for a in ('base','adapted')}
    for cid,c in cases.items():
        a=index[cid,'base'];b=index[cid,'adapted'];r=c['reference']
        if c['scope']=='current' and r['mode'] in ('known','positive','negative') and a['task_complete'] and not b['task_complete']:known_losses.append(cid)
        for arm in failures:
            if index[cid,arm]['verdict']!='pass':failures[arm].append(cid)
    for split in ('regression','test'):
        ids=[cid for cid,c in cases.items() if c['split']==split]
        effects[split]={}
        for metric in ('strict','task'):
            good=lambda cid,a:index[cid,a]['verdict']=='pass' if metric=='strict' else index[cid,a]['task_complete']
            effects[split][metric+'_corrections']=[cid for cid in ids if not good(cid,'base') and good(cid,'adapted')]
            effects[split][metric+'_regressions']=[cid for cid in ids if good(cid,'base') and not good(cid,'adapted')]
    gain=counts['test']['adapted']['strict_pass']-counts['test']['base']['strict_pass']
    rule={'heldout_strict_gain':gain,'required_gain':6,'heldout_gain_pass':gain>=6,
        'regression_strict_pass_to_fail':effects['regression']['strict_regressions'],
        'regression_preservation_pass':not effects['regression']['strict_regressions'],
        'known_current_required_answer_losses':known_losses,'known_control_preservation_pass':not known_losses}
    rule['pass']=rule['heldout_gain_pass'] and rule['regression_preservation_pass'] and rule['known_control_preservation_pass']
    clean={a:{s:counts[s][a]['strict_pass']==counts[s][a]['n'] for s in ('regression','test')} for a in ('base','adapted')}
    sensitivity={}
    for arm in ('base','adapted'):
        j=index['N01-1',arm]
        sensitivity[arm]={'regression_strict_pass':counts['regression'][arm]['strict_pass']+int(j['verdict']!='pass'),
            'regression_task_correct':counts['regression'][arm]['task_correct']+int(not j['task_complete'])}
    return {'status':'review_validated','author_review_only':True,'questions':144,'answer_captures':288,
        'counts':counts,'counts_by_kind':kinds,'counts_by_form':forms,'criteria_pass_counts':criteria,
        'matched_effects':effects,'predeclared_trainability_rule':rule,'clean_suite_gates':clean,'failures':failures,
        'n01_sensitivity':{'description':'Generously credit N01-1 under an epistemic refusal-to-assert reading; preserve all other judgments and the primary scores.','counts':sensitivity},
        'broader_retrieval_admission':False,'source_hashes':{str(p.relative_to(HERE)):sha(p) for p in (HERE/'review.json',HERE/'preflight/eval-cases.json',HERE/'preflight/freeze.json',HERE/'run/captures.json',HERE/'run/artifact-verification.json')}}

if __name__=='__main__':
    result=summarize()
    if (HERE/'result-manifest.json').exists():assert read(HERE/'summary.json')==result
    else:(HERE/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
