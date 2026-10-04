"""Validate the explicit author judgments and summarize the frozen comparisons."""
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant',
        'ownership_correct','body_valid','within_90_words')


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def summarize():
    artifact=read(HERE/'run/artifact-verification.json');assert artifact['status']=='PASS' and artifact['complete']
    captures=read(HERE/'run/captures.json');cases={c['id']:c for c in read(HERE/'preflight/cases.json')}
    review=read(HERE/'review.json')
    assert review['captures_sha256']==sha(HERE/'run/captures.json')
    assert review['cases_sha256']==sha(HERE/'preflight/cases.json')
    assert review['reviewer'] and review['model_version'] and review['process_notes']
    assert len(review['answers'])==len(captures)==96
    counts=defaultdict(Counter);byclass=defaultdict(lambda:defaultdict(Counter));criteria=defaultdict(Counter);states={}
    for c,j in zip(captures,review['answers']):
        assert (c['id'],c['arm'])==(j['id'],j['arm'])
        assert all(j[k] is None or type(j[k]) is bool for k in FIELDS)
        assert j['body_valid']==c['body_structurally_valid'] and j['within_90_words']==c['within_90_words']
        assert j['verdict'] in ('pass','fail','ambiguous') and j['reason'] and j['evidence']
        if j['verdict']=='pass':assert all(j[k] is True for k in FIELDS)
        if j['verdict']=='fail':assert any(j[k] is False for k in FIELDS)
        case=cases[c['id']]
        for e in j['evidence']:
            assert set(e)=={'where','index','quote'} and type(e['index']) is int and e['quote']
            if e['where']=='history':rows=case['history']
            elif e['where']=='reader_message':rows=c['messages']
            elif e['where']=='answer':rows=[{'content':c['text']}]
            else:raise ValueError('evidence location')
            assert 0<=e['index']<len(rows) and e['quote'] in rows[e['index']]['content']
        counts[c['arm']][j['verdict']]+=1;byclass[case['kind']][c['arm']][j['verdict']]+=1
        states[(c['id'],c['arm'])]=j['verdict']
        for k in FIELDS:criteria[k][str(j[k]).lower()]+=1
    effects={}
    for wrapper in ('plain','json'):
        transitions=Counter(states[(cid,wrapper+'_withdrawals_last')]+' -> '+states[(cid,wrapper+'_chronological')] for cid in cases)
        fixes=sum(states[(cid,wrapper+'_withdrawals_last')]=='fail' and states[(cid,wrapper+'_chronological')]=='pass' for cid in cases)
        regressions=sum(states[(cid,wrapper+'_withdrawals_last')]=='pass' and states[(cid,wrapper+'_chronological')]!='pass' for cid in cases)
        effects[wrapper]={'from_withdrawals_last_to_chronological':transitions,'failures_fixed':fixes,
                         'new_nonpasses':regressions,'predeclared_order_help_criterion':fixes>0 and regressions==0}
    result={'status':'review_validated','captures':96,'cases':24,'author_review_only':True,
        'counts_by_arm':counts,'counts_by_case_class_and_arm':byclass,'criterion_counts':criteria,
        'order_effects':effects,'primary_json_chronological_24_of_24':counts['json_chronological']['pass']==24,
        'training_admission':False,'training_labels':0,'source_hashes':{
            'captures.json':sha(HERE/'run/captures.json'),'cases.json':sha(HERE/'preflight/cases.json'),
            'review.json':sha(HERE/'review.json'),'preflight-freeze.json':sha(HERE/'preflight/freeze.json')}}
    return result


def main():
    result=summarize()
    if (HERE/'result-manifest.json').exists():
        assert read(HERE/'summary.json')==result, 'Frozen summary differs from reviewed answers'
    else:
        (HERE/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
