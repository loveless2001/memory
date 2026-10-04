"""Reconstruct captured prompts, source events, states and accounting offline."""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PREP=HERE/'preflight';RUN=HERE/'run'
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import answer_prefix_ids,strict_body_capture
from experiments.context_policy.preflight import digest
from experiments.context_policy.reader_state_protocol import parse_events,resolve,record_for_question,state_messages,semantic_events


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def verify():
    launch=read(RUN/'launch.json');manifest=read(RUN/'manifest.json');status=read(RUN/'status.json')
    for n,h in read(RUN/'artifact-hashes.json').items():
        assert Path(n).name==n and sha(RUN/n)==h,n
    for k in ('source_hashes','input_hashes','runner_sha256','freeze_sha256'):assert launch[k]==manifest[k],k
    assert manifest['source_hashes']==read(PREP/'runtime-sources.json')
    assert not manifest['final_answer_references_mounted'] and not manifest['raw_gold_events_mounted']
    assert manifest['oracle_state_in_oracle_messages'] and manifest['planned_captures']==288 and manifest['planned_extractions']==52
    assert manifest['hard_timeout_seconds']==1800 and manifest['retries']==0
    assert set(manifest['input_hashes'])=={'runtime-config.json','static-inputs.json','streams.json','questions.json','gate-requests.json'}
    assert sha(PREP/'freeze.json')==launch['freeze_sha256']
    for n,h in read(PREP/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
    protected=read(PREP/'protected.json')
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    for n,h in launch['source_hashes'].items():assert sha(RUN/'source-snapshot'/n)==h,n
    assert sha(RUN/'source-snapshot/modal-runners/modal-reader-state.py')==launch['runner_sha256']
    for n,h in launch['input_hashes'].items():assert sha(PREP/n)==h,n
    config=read(PREP/'runtime-config.json')
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    runtime=read(RUN/'runtime.json')
    assert runtime['model_revision']==config['model_revision'] and runtime['template_sha256']==digest(tok.chat_template)
    assert runtime['torch'].split('+')[0]=='2.7.1' and runtime['transformers']=='4.55.2'
    assert runtime['dtype']=='float32' and runtime['attention']=='math' and not runtime['tf32'] and runtime['trainable_parameters']==0
    static={r['request_id']:r for r in read(PREP/'static-inputs.json')}
    streams=read(PREP/'streams.json');stream_map={s['id']:s for s in streams}
    questions=read(PREP/'questions.json');cases={c['id']:c for c in read(PREP/'cases.json')}
    gold=read(PREP/'gold-events.json')
    accounting=defaultdict(lambda:Counter())

    def capture(c,row,limit):
        assert (c['request_id'],c['id'],c['arm'])==(row['request_id'],row['id'],row['arm'])
        assert c['messages']==row['messages'] and c['input_tokens']==len(answer_prefix_ids(tok,c['messages']))
        if 'input_tokens' in row:assert c['input_tokens']==row['input_tokens']
        assert c['output_limit']==limit and 0<len(c['token_ids'])<=limit and tok.eos_token_id not in c['token_ids'][:-1]
        body=strict_body_capture(tok,c['token_ids'],tok.eos_token_id)
        for k,v in body.items():assert c[k]==v,(c['request_id'],k)
        assert c['fresh_prefill'] and c['actual_forwarded_tokens']==c['input_tokens']+len(c['token_ids'])-int(c['ended_at_eos'])
        assert c['input_tokens']+limit<=config['active_context_max_tokens']
        a=accounting[c['arm']];a['calls']+=1;a['input_tokens']+=c['input_tokens'];a['generated_tokens']+=len(c['token_ids'])
        a['forwarded_tokens']+=c['actual_forwarded_tokens'];a['generation_seconds']+=c['elapsed_seconds']

    extractions=read(RUN/'extractions.json') if (RUN/'extractions.json').exists() else []
    assert len(extractions)<=len(streams)
    extracts={};exact_events=[];exact_states=[]
    for c,s in zip(extractions,streams):
        capture(c,static['extract:'+s['id']],768)
        parsed=parse_events(c['text'],s['history'])
        if not c['ended_at_eos'] or not c['body_structurally_valid']:
            parsed={'valid':False,'events':[],'error':'incomplete or invalid extraction body'}
        assert c['parsed']==parsed and c['resolved_state']==resolve(parsed['events'],s['property'])
        extracts[s['id']]=c
        exact_events.append(parsed['valid'] and semantic_events(parsed['events'])==semantic_events(gold[s['id']]['events']))
        exact_states.append(c['resolved_state']==gold[s['id']]['state'])
    dynamic={}
    if len(extractions)==52:
        for q in questions:
            s=stream_map[q['stream_id']]
            # Recreate the runtime insertion order before rendering JSON text.
            # Saved artifact objects are canonicalized with sorted dictionary keys.
            state=resolve(extracts[s['id']]['parsed']['events'],s['property'])
            record=record_for_question(state,s['history'],q)
            row={'request_id':'extracted:'+q['id'],'id':q['id'],'arm':'extracted',
                 'messages':state_messages(record,q['query']),'record':record}
            dynamic[q['id']]=row
        if (RUN/'derived-inputs.json').exists():assert list(dynamic.values())==read(RUN/'derived-inputs.json')
    checks=read(RUN/'cache-checks.json');gates=read(PREP/'gate-requests.json')
    expected_checks=gates['static']+['extracted:'+cid for cid in gates['extracted']]
    assert [c['request_id'] for c in checks]==expected_checks[:len(checks)]
    for c in checks:
        row=dynamic[c['request_id'].split(':',1)[1]] if c['arm']=='extracted' else static[c['request_id']]
        assert c['messages']==row['messages'] and c['arm']==row['arm']
        assert c['pass']==(c['initial_argmax_equal'] and c['cached_tokens']==c['fresh_tokens'])
        assert 0<len(c['cached_tokens'])<=16 and 0<len(c['fresh_tokens'])<=16
    assert not extractions or len(checks)>=30 and all(c['pass'] for c in checks[:30])
    answers=read(RUN/'captures.json') if (RUN/'captures.json').exists() else []
    assert len(answers)<=288
    expected=[]
    for i,q in enumerate(questions):
        arms=['baseline','oracle','extracted'];arms=arms[i%3:]+arms[:i%3]
        expected.extend((q,arm) for arm in arms)
    for c,(q,arm) in zip(answers,expected):
        row=dynamic[q['id']] if arm=='extracted' else static[arm+':'+q['id']]
        capture(c,row,192)
    old={c['id']:c for c in read(ROOT/'plans/260911-reader-repair/combined/captures.json') if c['arm']=='baseline'}
    reproduction=[]
    for c in answers:
        if c['arm']=='baseline' and c['id'] in old:
            assert c['messages']==old[c['id']]['messages']
            reproduction.append({'id':c['id'],'tokens_equal':c['token_ids']==old[c['id']]['token_ids']})
    complete=status['status']=='collection_complete'
    if complete:
        assert len(answers)==status['captures']==288 and len(extractions)==status['extractions']==52
        assert len(checks)==40 and all(c['pass'] for c in checks)
        assert Counter(c['arm'] for c in checks)=={'baseline':10,'oracle':10,'extract':10,'extracted':10}
        assert read(RUN/'cache-verdict.json')==status['gate'] and status['gate']['pass']
        assert status['training_labels']==0 and status['valid_extraction_parses']==sum(c['parsed']['valid'] for c in extractions)
        assert status['body_valid']==sum(c['body_structurally_valid'] for c in answers)
        assert status['within_90_words']==sum(c['within_90_words'] for c in answers)
    return {'status':'PASS','remote_status':status['status'],'complete':complete,
        'answers':len(answers),'extractions':len(extractions),'cache_checks':len(checks),
        'cache_per_workload':dict(Counter(c['arm'] for c in checks)),
        'body_valid_answers':sum(c['body_structurally_valid'] for c in answers),
        'answers_within_90_words':sum(c['within_90_words'] for c in answers),
        'max_answer_words':max((c['word_count_whitespace'] for c in answers),default=0),
        'valid_extraction_parses':sum(c['parsed']['valid'] for c in extractions),
        'exact_categorical_event_matches':sum(exact_events),'exact_resolved_state_matches':sum(exact_states),
        'protected_files_unchanged':len(protected),'prior_baseline_reproduction':reproduction,
        'identical_prior_baseline_sequences':sum(x['tokens_equal'] for x in reproduction),
        'accounting_by_workload':dict(accounting),'semantic_review':None,'training_labels':0}


if __name__=='__main__':
    result=verify()
    if (HERE/'result-manifest.json').exists():assert read(RUN/'artifact-verification.json')==result
    else:(RUN/'artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
