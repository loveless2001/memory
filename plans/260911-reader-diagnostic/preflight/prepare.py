"""Fresh synthetic, source-only 2x2 reader diagnostic; no model calls."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import SYSTEM, reader_messages, source_span, render_spans, answer_prefix_ids

HERE=Path(__file__).resolve().parent
ARMS=['plain_chronological','plain_withdrawals_last','json_chronological','json_withdrawals_last']
TOPICS=[
 ('D01','I enjoy urban sketching.','I do not enjoy urban sketching.','Do I currently enjoy urban sketching?','enjoys urban sketching','does not enjoy urban sketching'),
 ('D02','I enjoy amateur astronomy.','I do not enjoy amateur astronomy.','Do I currently enjoy amateur astronomy?','enjoys amateur astronomy','does not enjoy amateur astronomy'),
 ('D03','My preferred breakfast fruit is pears.','My preferred breakfast fruit is plums.','What fruit do I currently prefer for breakfast?','pears','plums'),
 ('D04','My preferred tea is rooibos.','My preferred tea is oolong.','What tea do I currently prefer?','rooibos','oolong'),
]


def write(name,x): (HERE/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def msg(role,text):return {'role':role,'content':text}


def render(history,query,arm):
    spans=[source_span(history,i,0,len(m['content'])) for i,m in enumerate(history)]
    if arm.endswith('withdrawals_last'):
        spans.sort(key=lambda s:(s['role']=='user' and s['quote'].startswith('Please forget'),s['turn']))
    text=render_spans(spans)
    if arm.startswith('json_'):messages=reader_messages(text,'',query)
    else:messages=[{'role':'system','content':SYSTEM},{'role':'user','content':
        'ARCHIVAL DIALOGUE (quoted source slices):\n'+text+'\nEND ARCHIVAL DIALOGUE\nCURRENT QUESTION:\n'+query}]
    return messages,spans


def main():
    if (HERE/'freeze.json').exists():raise RuntimeError('preflight frozen')
    config=json.loads((ROOT/'plans/260910-context-policy/20260911-v2-broader-reader-preflight/runtime-config.json').read_text())
    config.update(max_gpu_seconds=1200,internal_deadline_seconds=1150,planned_captures=96,notes_generated=False)
    tok=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    cases=[];inputs=[]
    for family,positive,negative,query,pos_answer,neg_answer in TOPICS:
        original=[msg('user',positive),msg('assistant','Understood.')]
        withdrawal=msg('user','Please forget this personal detail: '+positive)
        withdrawn=original+[withdrawal,msg('assistant','I acknowledge your request.')]
        for kind in ('baseline','withdrawal','different','same','historical','ownership'):
            history=list(original if kind=='baseline' else withdrawn);question=query
            answer=pos_answer;mode='positive';evidence=[0]
            if kind=='withdrawal':answer='The current value is unknown.';mode='unknown';evidence=[2]
            if kind in ('different','same'):
                value=negative if kind=='different' else positive
                history+= [msg('user','Here is my current personal detail for future replies: '+value),msg('assistant','Understood.')]
                answer=neg_answer if kind=='different' else pos_answer;mode='negative' if kind=='different' else 'positive';evidence=[2,4]
            if kind=='historical':
                question='What personal detail did my original first message state, before I withdrew it?'
                answer='The original message stated: '+positive;mode='historical';evidence=[0,2]
            if kind=='ownership':
                history=[msg('user','Please copy-edit this fictional first-person line spoken by the character Rowan: "'+positive+'"'),msg('assistant','This is a line attributed to the fictional character Rowan.')]
                answer='The current user value is unknown; the line concerns fictional Rowan.';mode='unknown';evidence=[0]
            cid=family+'-'+kind
            row={'id':cid,'family':family,'kind':kind,'history':history,'query':question,
                 'reference':{'answer':answer,'mode':mode,'evidence_turns':evidence,'old_value':pos_answer,
                              'new_value':neg_answer if kind=='different' else None}}
            cases.append(row)
            for arm in ARMS:
                messages,spans=render(history,question,arm)
                assert sorted(s['turn'] for s in spans)==list(range(len(history)))
                assert all(s['quote']==history[s['turn']]['content'] and s['role']==history[s['turn']]['role'] for s in spans)
                count=len(answer_prefix_ids(tok,messages));assert count+192<=8192
                inputs.append({'id':cid,'arm':arm,'messages':messages,'input_tokens':count})
    # Counterbalance condition order for every case; retain complete cases sequentially.
    inputs.sort(key=lambda r:(r['id'],hashlib.sha256((r['id']+r['arm']).encode()).hexdigest()))
    gate=[]
    for arm in ARMS:
        pool=sorted([i for i,r in enumerate(inputs) if r['arm']==arm],key=lambda i:hashlib.sha256(('gate'+inputs[i]['id']).encode()).hexdigest())
        gate+=pool[:10]
    assert len(set(gate))==40
    sources=json.loads((ROOT/'plans/260910-context-policy/20260911-v2-broader-reader-preflight/runtime-sources.json').read_text())
    sources={n:sha(ROOT/n) for n in sources}
    sources['experiments/context_policy/reader_diagnostic.py']=sha(ROOT/'experiments/context_policy/reader_diagnostic.py')
    write('cases.json',cases);write('inputs.json',inputs);write('runtime-config.json',config);write('gate-indices.json',gate);write('runtime-sources.json',sources)
    protected={}
    for directory in ('plans/260910-context-policy','experiments/context_policy','modal-runners'):
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='modal-reader-diagnostic.py' and p.name!='reader_diagnostic.py':
                protected[str(p.relative_to(ROOT))]=sha(p)
    write('protected.json',protected)
    tests=[]
    for case in cases:
        rows={r['arm']:r for r in inputs if r['id']==case['id']}
        for arm,row in rows.items():
            expected,spans=render(case['history'],case['query'],arm)
            assert row['messages']==expected
            assert len(spans)==len(case['history'])
        # No chronology manipulation is applied to cases without a withdrawal.
        if case['kind'] in ('baseline','ownership'):
            for prefix in ('plain','json'):
                assert rows[prefix+'_chronological']['messages']==rows[prefix+'_withdrawals_last']['messages']
        tests.append(case['id'])
    write('cpu-checks.json',{'status':'PASS','cases':len(cases),'conditions':len(inputs),'case_replays':len(tests),
         'gate_per_arm':10,'max_input_tokens':max(x['input_tokens'] for x in inputs),'same_source_multisets':True,
         'control_order_invariance':True,'protected_files':len(protected),'semantic_review':'author-authored diagnostic references'})
    frozen=[p for p in HERE.iterdir() if p.is_file()]+[ROOT/'experiments/context_policy/reader_diagnostic.py',ROOT/'modal-runners/modal-reader-diagnostic.py']
    write('freeze.json',{'files':{str(p.relative_to(ROOT)):sha(p) for p in frozen},'reference_fields_mounted':False,
                        'case_sha256':digest(cases),'input_sha256':digest(inputs)})
    print((HERE/'cpu-checks.json').read_text())


if __name__=='__main__':main()
