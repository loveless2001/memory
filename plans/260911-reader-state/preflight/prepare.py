"""Prepare and freeze the authorized state diagnostic without model inference."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = ROOT/'plans/260911-reader-repair'
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(HERE))
from author import make_cases
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import answer_prefix_ids
from experiments.context_policy.reader_state_protocol import (
    validate_events, resolve, record_for_question, archive_messages, extraction_messages, state_messages)


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,x): (HERE/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def key(x): return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def construct(tok):
    cases=make_cases(); streams=[]; stream_index={}; questions=[]; inputs=[]; gold={}
    old={(c['id'],c['arm']):c for c in read(PARENT/'preflight/inputs.json')}
    for case in cases:
        stream_key=key([case['history'],case['property']])
        if stream_key not in stream_index:
            sid='S'+str(len(streams)+1).zfill(3); stream_index[stream_key]=sid
            stream={'id':sid,'history':case['history'],'property':case['property']}
            events=validate_events(case['gold_events'],case['history'])
            state=resolve(events,case['property'])
            streams.append(stream);gold[sid]={'events':events,'state':state,'raw':case['gold_events']}
            messages=extraction_messages(stream['history'],stream['property'])
            inputs.append({'request_id':'extract:'+sid,'id':sid,'arm':'extract','messages':messages,
                           'input_tokens':len(answer_prefix_ids(tok,messages))})
        sid=stream_index[stream_key];case['stream_id']=sid
        assert case['gold_events']==gold[sid]['raw']
        q={k:case[k] for k in ('id','stream_id','query','property','scope','target_turn')}
        questions.append(q)
        for arm,messages in [('baseline',archive_messages(case['history'],case['query'])),
                ('oracle',state_messages(record_for_question(gold[sid]['state'],case['history'],q),case['query']))]:
            if case['split']=='regression' and arm=='baseline': assert messages==old[case['id'],'baseline']['messages']
            inputs.append({'request_id':arm+':'+case['id'],'id':case['id'],'arm':arm,'messages':messages,
                           'input_tokens':len(answer_prefix_ids(tok,messages))})
        if case['split']=='new':
            state=gold[sid]['state'];ref=case['reference']
            assert state['status']==('unknown' if ref['current_value'] is None and ref['polarity'] is None else 'known')
            assert state['value']==ref['current_value'] and state['polarity']==ref['polarity']
    assert len(cases)==96 and len(streams)==52 and len(inputs)==244
    gate=[]
    for arm in ('baseline','oracle','extract'):
        pool=sorted([r['request_id'] for r in inputs if r['arm']==arm],key=lambda x:key(['gate',x]))
        gate.extend(pool[:10])
    derived=sorted([q['id'] for q in questions],key=lambda x:key(['gate','extracted',x]))[:10]
    return cases,streams,questions,inputs,gold,{'static':gate,'extracted':derived}


def main(freeze=False):
    assert not (HERE/'freeze.json').exists(), 'Frozen input is immutable'
    config=read(PARENT/'preflight/runtime-config.json')
    config.update(max_gpu_seconds=1800,internal_deadline_seconds=1750,planned_captures=288,
                  planned_extractions=52,extraction_output_tokens=768,notes_generated=False,
                  diagnostic='conditional_event_extraction_and_state_answering')
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    cases,streams,questions,inputs,gold,gates=construct(tok)
    sources=read(PARENT/'preflight/runtime-sources.json')
    for n in ('experiments/context_policy/reader_state.py','experiments/context_policy/reader_state_protocol.py'):
        sources[n]=sha(ROOT/n)
    for n,h in sources.items(): assert sha(ROOT/n)==h,n
    protected={}
    excluded={'reader_state.py','reader_state_protocol.py','modal-reader-state.py','test_context_policy_reader_state.py'}
    for directory in ('plans/260910-context-policy','plans/260911-reader-diagnostic','plans/260911-reader-repair',
                      'plans/260911-reader-qwen3-8b','experiments/context_policy','modal-runners','tests'):
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and not {'__pycache__','.cache'}.intersection(p.parts) and p.suffix!='.pyc' and p.name not in excluded:
                protected[str(p.relative_to(ROOT))]=sha(p)
    for n,x in [('cases.json',cases),('streams.json',streams),('questions.json',questions),('static-inputs.json',inputs),
                ('gold-events.json',gold),('gate-requests.json',gates),('runtime-config.json',config),
                ('runtime-sources.json',sources),('protected.json',protected)]: write(n,x)
    assert all(r['input_tokens']+(768 if r['arm']=='extract' else 192)<=8192 for r in inputs)
    checks={'status':'PASS','cases':96,'regression_cases':72,'new_cases':24,'new_histories':12,
            'unique_extraction_streams':52,'answer_captures':288,'model_calls':340,'cache_fixtures':40,
            'unchanged_prior_baseline_messages':72,'max_static_input_tokens':max(r['input_tokens'] for r in inputs),
            'protected_files':len(protected),'historical_controls':sum(c['scope']=='historical' for c in cases),
            'reference_review':'unblinded author review before inference; not independent',
            'model_template_sha256':hashlib.sha256(tok.chat_template.encode()).hexdigest()}
    write('cpu-checks.json',checks)
    if freeze:
        assert (HERE/'REFERENCE-REVIEW.md').exists() and (HERE/'test-results.json').exists()
        assert read(HERE/'test-results.json')['passed'] is True
        paths=[p for p in HERE.iterdir() if p.is_file()]
        paths += [ROOT/n for n in (*sources,'modal-runners/modal-reader-state.py','tests/test_context_policy_reader_state.py')]
        write('freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),
            'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},
            'oracle_state_in_oracle_messages':True,'raw_gold_events_mounted':False,'final_answer_references_mounted':False,
            'parent_result_manifest_sha256':sha(PARENT/'result-manifest.json')})
    print(json.dumps(checks,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();main(args.freeze)
