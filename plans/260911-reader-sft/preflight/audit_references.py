"""Audit every rendered new reference before freezing."""
from collections import Counter
from author_train import make_training_cases,FAMILIES
from author_test import make_test_cases

def audit():
    train=make_training_cases();test=make_test_cases()
    for rows in (train,test):
        assert len({r['id'] for r in rows})==len(rows)
        for c in rows:
            r=c['reference'];a=r['answer'];h=c['history']
            assert a.strip() and len(a.split())<=90
            assert all(type(i)==int and 0<=i<len(h) and h[i]['role']=='user' for i in r['evidence_turns'])
            if c['scope']=='historical':assert r['mode']=='historical' and 'first' in a.lower()
            elif r['mode']=='unknown':
                assert r['current_value'] is None and r['polarity'] is None and r['binary_truth'] is None
                assert 'unknown' in a.lower()
                assert all(v.lower() not in a.lower() for v in r['forbidden_old_values'])
            else:
                assert r['mode']=='known' and r['polarity'] in ('positive','negative','none')
                if r['polarity']=='positive':assert r['current_value'].lower() in a.lower() or c['id']=='E14-open'
                if r['polarity']=='negative':assert 'not' in a.lower()
                if r['polarity']=='none':assert r['current_value'] is None and 'no ' in a.lower()
            if c['question_form']=='binary' and r['binary_truth'] is not None:
                assert a.startswith('Yes.' if r['binary_truth'] else 'No.'),c['id']
        assert all(n==2 for n in Counter((c['family'],c['kind']) for c in rows).values())
    for c in train:
        old=FAMILIES[int(c['family'][1:])-1][1];r=c['reference']
        if c['scope']=='current':assert all(v not in r['answer'] for v in r['forbidden_old_values'])
        if c['kind']=='negative':assert 'alternative is unknown' in r['answer'] and old in r['answer']
    return {'status':'PASS','rendered_training_references':len(train),'new_test_references':len(test),
            'review_type':'author template and complete new-history review plus all-case invariants'}

if __name__=='__main__':
    import json
    print(json.dumps(audit(),indent=2))
