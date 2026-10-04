"""Verify preserved inputs, the author overlay, and exact review projection."""
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PACKET=HERE.with_name('20260911-v2-broader-answer-review')
AUDIT=HERE.with_name('20260911-v2-broader-review-audit')


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def main():
    for name,expected in read(HERE/'freeze.json')['files'].items():
        p=Path(name)
        assert not p.is_absolute() and '..' not in p.parts
        assert sha(ROOT/p)==expected,name
    subprocess.run([sys.executable,str(AUDIT/'verify_corrections.py'),'--corrections',
                    str(AUDIT/'review/corrections.json')],check=True,capture_output=True,text=True)
    parent=read(HERE/'claude-corrected-review.json');final=read(HERE/'adjudicated-review.json')
    patch=read(HERE/'adjudication.json');summary=read(HERE/'summary.json')
    assert patch['parent_review_sha256']==sha(HERE/'claude-corrected-review.json')
    assert final['author_adjudication']['sha256']==sha(HERE/'adjudication.json')
    prior={a['answer_id']:a for c in parent['cases'] for a in c['answers']}
    expected=copy.deepcopy(parent);replacements={};seen=set();changes=Counter()
    for row in patch['decisions']:
        aid=row['answer_id'];assert aid not in seen;seen.add(aid)
        assert digest(prior[aid])==row['parent_judgment_sha256']
        if row['decision']=='retain':
            assert aid=='C073-B' and row['replacement'] is None and not row['changed_criteria']
            continue
        assert row['decision']=='replace'
        replacement=row['replacement'];assert replacement['answer_id']==aid
        assert replacement['verdict']==prior[aid]['verdict']
        differences={k for k in replacement if replacement[k]!=prior[aid][k]}
        assert differences <= {'supported_in_visible_state','task_complete','reason','evidence'}
        for field,change in row['changed_criteria'].items():
            assert prior[aid][field]==change['before'] and replacement[field]==change['after']
            changes[field]+=1
        assert replacement['supported_in_visible_state'] is False
        if 'task_complete' in differences:assert aid in ('C020-B','C020-C') and replacement['task_complete'] is True
        replacements[aid]=replacement
    assert len(seen)==20 and len(replacements)==19
    for case in expected['cases']:
        case['answers']=[replacements.get(a['answer_id'],a) for a in case['answers']]
    assert expected['cases']==final['cases'],'review projection changed unrelated judgments'
    assert changes=={'supported_in_visible_state':19,'task_complete':2}
    checked=subprocess.run([sys.executable,str(PACKET/'validate.py'),'--review',str(HERE/'adjudicated-review.json')],
                           check=True,capture_output=True,text=True)
    validation=json.loads(checked.stdout)
    assert validation['verdict_counts']==summary['verdicts']
    for field,counts in summary['criteria'].items():
        assert dict(Counter(str(a[field]).lower() for c in final['cases'] for a in c['answers']))==counts
    result={'status':'PASS','answers_verified':262,'overlay_entries':20,'criteria_changes':dict(changes),
        'verdicts':validation['verdict_counts'],'original_and_correction_reviews_preserved':True,
        'unrelated_judgments_unchanged':True,'semantic_truth_certified':False,'training_labels':0}
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
