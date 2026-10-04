"""Audit the saved run without inferring semantic correctness or training labels."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from experiments.context_policy.broader_protocol import reader_messages, append_evidence, answer_prefix_ids, strict_body_capture
from experiments.context_policy.broader_notes import source_candidates, pack_ranked_selection, validate_notes
from experiments.context_policy.grounded_notes import note_batches, render_notes
from experiments.context_policy.source_choice import choice_messages, SourceChoiceGrammar
from experiments.context_policy.preflight import canonical, digest, fixtures

HERE=Path(__file__).resolve().parent
PREP=HERE.with_name('20260911-v2-broader-reader-preflight')


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    hashes=read(HERE/'artifact-hashes.json');require(hashes is not None,'remote artifact manifest missing')
    for name,expected in hashes.items():
        path=Path(name)
        require(not path.is_absolute() and '..' not in path.parts,'unsafe artifact path')
        require(sha(HERE/path)==expected,'remote artifact hash mismatch: '+name)
    launch=read(HERE/'launch.json');manifest=read(HERE/'manifest.json');status=read(HERE/'status.json')
    require(status is not None,'remote terminal status missing')
    for key in ('source_hashes','input_hashes','runner_sha256','preflight_sha256'):
        require(launch[key]==manifest[key],'launch/remote binding mismatch: '+key)
    require(sha(PREP/'freeze.json')==manifest['preflight_sha256'],'preflight freeze mismatch')
    for name,expected in launch['source_hashes'].items():
        require(sha(HERE/'source-snapshot'/name)==expected,'source snapshot changed: '+name)
    require(sha(HERE/'source-snapshot/modal-runners/modal-broader-reader.py')==launch['runner_sha256'],'runner snapshot changed')
    for name,expected in launch['input_hashes'].items():require(sha(PREP/name)==expected,'frozen runtime input changed')
    for name,expected in read(PREP/'freeze.json')['files'].items():require(sha(ROOT/name)==expected,'prelaunch source/file changed: '+name)
    for name,expected in read(PREP/'protected-inputs.json').items():require(sha(ROOT/name)==expected,'prior protected artifact changed: '+name)
    config=read(PREP/'runtime-config.json');bundle=read(PREP/'reader-input.json');views=read(PREP/'reader-views.json')
    tokenizer=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    checks=read(HERE/'transcript-checks.json',[]);gate=read(HERE/'transcript-verdict.json',{})
    require([c['id'] for c in checks]==[r['id'] for r in fixtures()][:len(checks)],'cache fixture order')
    for c in checks:
        require(len(c['append_argmax_equal'])==4,'cache append stage coverage')
        equal=all(c['append_argmax_equal']) and c['cached_tokens']==c['fresh_tokens']
        require(c['equal']==equal,'cache comparison result inconsistent')
    passed=len(checks)==40 and all(c['equal'] for c in checks)
    if gate:require(gate['pass']==passed and gate['checked']==len(checks),'cache verdict inconsistent')
    runtime=read(HERE/'runtime.json',{})
    if runtime:
        require(runtime['model_revision']==config['model_revision'] and runtime['tokenizer_template_sha256']==digest(tokenizer.chat_template),'runtime model/template mismatch')
        require(runtime['torch'].split('+')[0]=='2.7.1' and runtime['transformers']=='4.55.2','runtime package mismatch')
        require(runtime['reader_dtype']=='float32' and runtime['reader_attention_backend']=='math' and runtime['reader_tf32'] is False,'runtime precision changed')
        require(runtime['trainable_parameters']==0,'unexpected trainable parameters')
    notes=read(HERE/'notes.json',{});events=read(HERE/'note-events.json',[]);captures=read(HERE/'captures.json',[])
    require(passed or not (notes or events or captures),'collection preceded passing cache gate')
    if notes:validate_notes(tokenizer,{hid:bundle['histories'][hid] for hid in notes},notes,config['notes_max_tokens'])
    # Replay only completed source choices. This checks actual prompts, branching
    # and admission, not whether the model made useful selections.
    cursor=0;replayed={};event_failure=None
    for work in read(PREP/'note-worklist.json'):
        if cursor>=len(events):break
        hid=work['history_id'];history=bundle['histories'][hid];parent=work['parent_history_id']
        candidates,constraints=source_candidates(tokenizer,history)
        previous=list(replayed[parent]['selected']) if parent else []
        if parent:candidates=[x for x in candidates if x['turn']>=len(bundle['histories'][parent])]
        batches=note_batches(tokenizer,candidates)
        require(len(batches)==work['updates'],'note workload mismatch')
        completed=True
        for batch_index,batch in enumerate(batches):
            if cursor>=len(events):completed=False;break
            e=events[cursor];cursor+=1
            through=len(history)-1 if batch_index==len(batches)-1 else batch[-1]['turn']
            ledger=[x for x in constraints if x['turn']<=through]
            expected=choice_messages(tokenizer,previous,batch,ledger,config['notes_max_tokens'])
            require(e['history_id']==hid and e['parent_history_id']==parent and e['batch']==batch_index and e['through_turn']==through,'note event order/branch mismatch')
            require(e['messages']==expected,'actual note selector prompt differs from source replay')
            require(e['input_tokens']==len(tokenizer.apply_chat_template(expected,tokenize=True,add_generation_prompt=True)),'selector input token mismatch')
            if e['accepted'] is None:
                require(cursor==len(events),'events follow unfinished selector');completed=False;event_failure='unfinished';break
            grammar=SourceChoiceGrammar(tokenizer,list(dict.fromkeys(x['id'] for x in previous+batch)))
            try:
                ranking=grammar.selected_ids(e['token_ids'])
                selected,text,admission=pack_ranked_selection(tokenizer,json.dumps(ranking),
                    bool(e['token_ids'] and e['token_ids'][-1]==tokenizer.eos_token_id),previous,batch,ledger,history,
                    config['notes_max_tokens'],through_turn=through)
            except (ValueError,KeyError,TypeError):
                require(e['accepted'] is False and cursor==len(events),'unexpected selector validation failure')
                completed=False;event_failure='reproduced_validation_failure';break
            require(e['accepted'] is True and e['admission']==admission,'note admission differs')
            previous=selected
        if not completed:break
        expected_note={'text':text,'selected':previous,'withdrawals':constraints,'tokens':len(tokenizer.encode(text,add_special_tokens=False)),
                       'semantic_review':'pending','history_sha256':digest(history)}
        require(notes.get(hid)==expected_note,'saved note differs from event replay')
        replayed[hid]=expected_note
    require(cursor==len(events) and set(replayed)==set(notes),'note artifact coverage mismatch')
    expected_order=[(s['id'],n) for s in read(PREP/'schedule.json') for n in s['round_order']]
    require([(c['id'],c['retrieval_rounds']) for c in captures]==expected_order[:len(captures)],'capture ordering/coverage changed')
    if captures:require(len(notes)==60,'answers collected before all notes completed')
    questions={q['id']:q for q in bundle['questions']}
    for c in captures:
        q=questions[c['id']];hid=q['persona_id'];n=c['retrieval_rounds'];v=views[c['id']]
        messages=reader_messages(notes[hid]['text'],v['recent']['text'],q['query']['content'])
        for ret in v['retrievals'][:n]:messages=append_evidence(messages,ret['text'],q['query']['content'])
        require(c['messages']==messages and c['retrieval']==v['retrievals'][:n],'actual reader view differs from replay')
        require(c['persona_id']==hid and c['arm']=='raw_source' and c['fresh_prefill'] is True,'capture condition changed')
        count=len(answer_prefix_ids(tokenizer,messages));require(c['input_tokens']==count,'reader input token mismatch')
        require(count+config['max_message_output_tokens']<=config['active_context_max_tokens'],'reader context overflow')
        require(0<len(c['token_ids'])<=config['max_message_output_tokens'],'output token count')
        require(tokenizer.eos_token_id not in c['token_ids'][:-1],'tokens after EOS')
        body=strict_body_capture(tokenizer,c['token_ids'],tokenizer.eos_token_id)
        for key,value in body.items():require(c[key]==value,'saved body validation/decode mismatch: '+key)
        expected_forwarded=count+len(c['token_ids'])-int(c['ended_at_eos'])
        require(c['actual_forwarded_tokens']==expected_forwarded,'fresh prefill token accounting mismatch')
    complete=status['status']=='awaiting_independent_answer_review'
    if complete:require(len(captures)==360 and len(notes)==60 and len(events)==171 and event_failure is None,'terminal completion incomplete')
    result={'status':'PASS','remote_status':status['status'],'app_id':launch['app_id'],'artifact_files_verified':len(hashes),
        'cache_checks':len(checks),'cache_passes':sum(c['equal'] for c in checks),'cache_gate_pass':passed,
        'notes_verified':len(notes),'selector_events_replayed':len(events),'selector_failure':event_failure,
        'captures_verified':len(captures),'collection_complete':complete,
        'body_structurally_valid':sum(c['body_structurally_valid'] for c in captures),
        'within_90_words':sum(c['within_90_words'] for c in captures),
        'max_answer_words':max((c['word_count_whitespace'] for c in captures),default=None),
        'independent_answer_review':'pending' if captures else 'no answers collected',
        'semantic_accuracy':None,'training_labels':0}
    (HERE/'artifact-verification.json').write_bytes(canonical(result))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
