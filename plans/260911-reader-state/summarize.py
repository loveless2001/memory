"""Validate explicit author judgments and summarize the frozen diagnostic."""
import hashlib
import json
from pathlib import Path
from collections import Counter,defaultdict

HERE=Path(__file__).resolve().parent
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant',
        'ownership_correct','body_valid','within_90_words')


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def validate_evidence(evidence,capture,history):
    assert evidence
    kinds=set()
    for e in evidence:
        assert set(e)=={'where','index','quote'} and type(e['index']) is int and e['quote']
        if e['where']=='answer':rows=[{'content':capture['text']}]
        elif e['where']=='history':rows=history
        elif e['where']=='reader_message':rows=capture['messages']
        else:raise ValueError(e['where'])
        assert 0<=e['index']<len(rows) and e['quote'] in rows[e['index']]['content']
        kinds.add(e['where'])
    assert {'answer','history','reader_message'}<=kinds


def summarize():
    artifact=read(HERE/'run/artifact-verification.json');assert artifact['status']=='PASS' and artifact['complete']
    cases={c['id']:c for c in read(HERE/'preflight/cases.json')}
    streams={s['id']:s for s in read(HERE/'preflight/streams.json')}
    captures=read(HERE/'run/captures.json');extractions=read(HERE/'run/extractions.json')
    review=read(HERE/'review.json');er=read(HERE/'extraction-review.json')
    assert review['status']==er['status']=='complete' and review['training_labels']==er['training_labels']==0
    assert review['captures_sha256']==sha(HERE/'run/captures.json') and review['cases_sha256']==sha(HERE/'preflight/cases.json')
    assert er['extractions_sha256']==sha(HERE/'run/extractions.json') and er['gold_events_sha256']==sha(HERE/'preflight/gold-events.json')
    assert len(review['answers'])==len(captures)==288 and len(er['streams'])==len(extractions)==52
    extracted_states={};extraction_scores=defaultdict(Counter)
    for c,j in zip(extractions,er['streams']):
        assert c['id']==j['id'] and j['reason']
        assert all(type(j[k]) is bool for k in ('semantic_events_correct','quotes_sufficient','resolved_state_correct'))
        assert j['schema_and_spans_valid']==c['parsed']['valid']
        if not c['parsed']['valid']:assert not j['semantic_events_correct'] and not j['quotes_sufficient']
        validate_evidence(j['evidence'],c,streams[c['id']]['history'])
        split=next(v['split'] for v in cases.values() if v['stream_id']==c['id'])
        for scope in (split,'all'):
            x=extraction_scores[scope];x['streams']+=1
            for field in ('schema_and_spans_valid','semantic_events_correct','quotes_sufficient','resolved_state_correct'):x[field]+=j[field]
        extracted_states[c['id']]=j
    counts=defaultdict(lambda:defaultdict(Counter));criteria=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    kinds=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    forms=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    scopes=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    prompt_support=defaultdict(lambda:defaultdict(Counter));decomposition=defaultdict(Counter)
    index={}
    for c,j in zip(captures,review['answers']):
        assert (c['id'],c['arm'])==(j['id'],j['arm']) and j['reason']
        assert all(type(j[k]) is bool for k in FIELDS)
        assert j['body_valid']==c['body_structurally_valid'] and j['within_90_words']==c['within_90_words']
        assert j['verdict']==('pass' if all(j[k] for k in FIELDS) else 'fail')
        assert j['state_prompt_supported'] is None if c['arm']=='baseline' else type(j['state_prompt_supported']) is bool
        case=cases[c['id']];validate_evidence(j['evidence'],c,case['history'])
        split,arm=case['split'],c['arm'];index[c['id'],arm]=j
        for group in (split,'all'):
            x=counts[group][arm];x['n']+=1;x['strict_pass']+=j['verdict']=='pass';x['task_correct']+=j['task_complete']
            y=scopes[group][case['scope']][arm];y['n']+=1;y['strict_pass']+=j['verdict']=='pass';y['task_correct']+=j['task_complete']
            for field in FIELDS:criteria[group][arm][field][str(j[field]).lower()]+=1
        for table,dim in ((kinds,case['kind']),(forms,case['question_form'])):
            cell=table[split][dim][arm];cell['n']+=1;cell['strict_pass']+=j['verdict']=='pass';cell['task_correct']+=j['task_complete']
        if arm!='baseline':prompt_support[split][arm][str(j['state_prompt_supported']).lower()]+=1
        if arm=='extracted' and case['scope']=='current':
            ej=extracted_states[case['stream_id']]
            key=('state_correct' if ej['resolved_state_correct'] else 'state_wrong')+' / '+('answer_correct' if j['task_complete'] else 'answer_wrong')
            decomposition[split][key]+=1
            if not ej['schema_and_spans_valid'] and j['task_complete']:decomposition[split]['invalid_extraction_but_correct_answer']+=1
            if ej['resolved_state_correct'] and j['verdict']!='pass':decomposition[split]['state_correct_but_strict_fail']+=1
    effects={}
    for split in ('regression','new'):
        effects[split]={}
        for scope in ('all','current','historical'):
            ids=[cid for cid,c in cases.items() if c['split']==split and (scope=='all' or c['scope']==scope)]
            effects[split][scope]={}
            for a,b in (('baseline','oracle'),('baseline','extracted'),('oracle','extracted')):
                effects[split][scope][a+'_to_'+b]={
                    'n':len(ids),
                    'strict_corrections':sum(index[cid,a]['verdict']!='pass' and index[cid,b]['verdict']=='pass' for cid in ids),
                    'strict_regressions':sum(index[cid,a]['verdict']=='pass' and index[cid,b]['verdict']!='pass' for cid in ids),
                    'task_corrections':sum(not index[cid,a]['task_complete'] and index[cid,b]['task_complete'] for cid in ids),
                    'task_regressions':sum(index[cid,a]['task_complete'] and not index[cid,b]['task_complete'] for cid in ids)}
    gates={arm:{'regression_72_of_72':counts['regression'][arm]['strict_pass']==72,
                'new_24_of_24':counts['new'][arm]['strict_pass']==24} for arm in ('baseline','oracle','extracted')}
    for gate in gates.values():gate['both_pass']=all(gate.values())
    sensitivity={}
    for arm in ('baseline','oracle','extracted'):
        n01=index['N01-1',arm]
        sensitivity[arm]={'n':24,'strict_pass':counts['new'][arm]['strict_pass']+int(n01['verdict']!='pass'),
                          'task_correct':counts['new'][arm]['task_correct']+int(not n01['task_complete'])}
    return {'status':'review_validated','author_review_only':True,'questions':96,'answer_captures':288,
        'extraction_streams':52,'counts':counts,'counts_by_scope':scopes,'counts_by_kind':kinds,'counts_by_form':forms,
        'criteria':criteria,'state_prompt_support':prompt_support,'extraction_scores':extraction_scores,
        'current_pipeline_decomposition':decomposition,'matched_effects':effects,'gates':gates,
        'n01_sensitivity':{'description':'Generously credit all three N01-1 binary responses under an epistemic refusal-to-assert reading; all other judgments unchanged. This is a disclosed post-review sensitivity, not a change to the frozen primary convention.',
                          'new_counts':sensitivity},
        'training_admission':False,'training_labels':0,
        'source_hashes':{str(p.relative_to(HERE)):sha(p) for p in (HERE/'review.json',HERE/'extraction-review.json',
            HERE/'preflight/cases.json',HERE/'preflight/gold-events.json',HERE/'preflight/freeze.json',
            HERE/'run/captures.json',HERE/'run/extractions.json',HERE/'run/artifact-verification.json')}}


if __name__=='__main__':
    result=summarize()
    if (HERE/'result-manifest.json').exists():assert read(HERE/'summary.json')==result
    else:(HERE/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
