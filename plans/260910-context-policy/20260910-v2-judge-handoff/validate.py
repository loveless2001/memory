"""Check frozen blind-packet integrity and optional independent-review structure."""
import argparse,json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[2]
CRITERIA=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct','body_valid','within_90_words')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def evidence(items,history,messages=None):
    assert isinstance(items,list)
    for item in items:
        assert set(item)=={'where','index','quote'}
        assert type(item['index']) is int and isinstance(item['quote'],str) and item['quote']
        if item['where']=='history':texts=[m['content'] for m in history['turns']]
        else:
            assert item['where']=='reader_message' and messages is not None
            texts=[m['content'] for m in messages]
        assert 0<=item['index']<len(texts) and item['quote'] in texts[item['index']], 'citation not found'
def main(review=None):
    manifest=read(BASE/'packet-manifest.json')
    for name,expected in manifest['source_files'].items():assert sha(ROOT/name)==expected,name
    for name,expected in manifest['packet_files'].items():assert sha(BASE/name)==expected,name
    assert sha(BASE/'sealed-map.json')==manifest['sealed_map_sha256']
    assert sha(BASE/'review-template.json')==manifest['template_sha256']
    index=read(BASE/'packet/index.json');assert len(index)==manifest['cases']==21
    answer_count=0
    for row in index:
        proposal=read(BASE/'packet'/row['reference_file']);answers=read(BASE/'packet'/row['answer_file'])
        assert proposal['case_id']==answers['case_id']==row['case_id']
        assert len(answers['answers'])==2
        answer_count+=len(answers['answers'])
    assert answer_count==manifest['answers']==42
    if review:
        output=read(Path(review))
        assert output['reviewer_model'].strip() and output['reviewed_at'].strip()
        assert type(output['prior_verdicts_seen']) is bool and isinstance(output['blinding_notes'],str)
        by_id={c['case_id']:c for c in output['cases']}
        assert len(by_id)==len(output['cases'])==21 and set(by_id)=={x['case_id'] for x in index}
        for row in index:
            case=by_id[row['case_id']]
            assert case['reference_verdict'] in ('accept','reject','ambiguous','insufficient_source')
            assert case['reference_reason'].strip()
            history=read(BASE/'packet/histories'/f"{row['history_id']}.json")
            evidence(case['reference_evidence'],history)
            actual=read(BASE/'packet'/row['answer_file'])['answers']
            judged={a['answer_id']:a for a in case['answers']}
            assert len(judged)==len(case['answers'])==2 and set(judged)=={a['answer_id'] for a in actual}
            for a in actual:
                j=judged[a['answer_id']]
                assert j['verdict'] in ('pass','fail','ambiguous','insufficient_source') and j['reason'].strip()
                assert all(type(j[k]) is bool or j[k] is None for k in CRITERIA)
                if j['verdict']=='pass':assert all(j[k] is True for k in CRITERIA)
                if j['verdict']=='fail':assert any(j[k] is False for k in CRITERIA)
                evidence(j['evidence'],history,a['actual_messages'])
    print(json.dumps(dict(status='pass',packet_cases=21,packet_answers=42,independent_review_file=str(review) if review else None,semantic_truth_verified=False)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--review',type=Path);args=p.parse_args();main(args.review)
