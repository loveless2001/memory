"""Replay the paired run against its prospective source and input freezes."""
import json
from pathlib import Path
from transformers import AutoTokenizer
from experiments.context_policy.preflight import canonical,digest
from experiments.context_policy.personamem import sha256
from experiments.context_policy.memory_probe import validate_reused_notes
from experiments.context_policy.reader_regression import paired_views,reader_messages,append_evidence,answer_prefix_ids,strict_body_capture
ROOT=Path(__file__).resolve().parents[3]
PLAN=Path(__file__).resolve().parent
RUN=PLAN.parent/'20260910-v2-withdrawal-regression'
DATA=PLAN.parent/'20260910-v2-withdrawal-regression-data'
def read(p):return json.loads(p.read_text())
def main():
    frozen=read(PLAN/'freeze.json');launch=read(RUN/'launch.json');artifacts=RUN/'artifacts'
    for name,sha in frozen['files'].items():
        path=RUN/'source-snapshot'/name if name in frozen['source_files'] else ROOT/name
        assert sha256(path.read_bytes())==sha,name
    assert launch['source_files']==frozen['source_files']
    assert launch['source_sha256']==digest(launch['source_files'])==frozen['source_sha256']
    for name,sha in launch['source_files'].items():assert sha256((RUN/'source-snapshot'/name).read_bytes())==sha
    hashes=read(artifacts/'artifact-hashes.json')
    for name,sha in hashes.items():assert sha256((artifacts/name).read_bytes())==sha,name
    manifest=read(artifacts/'manifest.json')
    assert manifest['source_files']==launch['source_files'] and manifest['no_references_mounted']
    assert manifest['input_hashes']==launch['input_hashes']
    for name,sha in launch['input_hashes'].items():assert sha256((DATA/name).read_bytes())==sha
    config=manifest['config'];bundle=read(DATA/'reader-input.json');notes=read(DATA/'notes.json');topics=read(DATA/'topics.json')
    tokenizer=AutoTokenizer.from_pretrained(config['model_id'],revision=config['model_revision'],local_files_only=True)
    check=validate_reused_notes(tokenizer,bundle,notes)
    assert check==read(artifacts/'reused-note-checks.json')
    gates=read(artifacts/'transcript-checks.json')
    assert len(gates)==40 and all(x['equal'] and all(x['append_argmax_equal']) and x['cached_tokens']==x['fresh_tokens'] for x in gates)
    assert read(artifacts/'transcript-verdict.json')['pass']
    contexts=read(DATA/'expected-contexts.json');captures=read(artifacts/'captures.json')
    assert len(captures)==len(contexts)==42
    verified=[]
    for q,row in zip(bundle['questions'],read(DATA/'schedule.json')):
        pid=q['persona_id'];query=q['query']['content']
        views=paired_views(tokenizer,bundle['histories'][pid],notes[pid],topics[pid],query,config)
        assert views['raw']['retrieval']['chunk_ids']==views['neutral']['retrieval']['chunk_ids']
        for arm in row['arm_order']:
            view=views[arm];n=row['retrieval_rounds'];i=len(verified);capture=captures[i];context=contexts[i]
            messages=reader_messages(view['notes'],view['recent'],query)
            if n:messages=append_evidence(messages,view['retrieval']['text'],query)
            assert context['view']==view and context['messages']==messages==capture['messages']
            assert capture['id']==context['id']==q['id'] and capture['arm']==context['arm']==arm
            assert capture['retrieval_rounds']==context['retrieval_rounds']==n and capture['kind']==row['kind']
            assert capture['retrieval']==([view['retrieval']] if n else [])
            ids=answer_prefix_ids(tokenizer,messages)
            assert len(ids)==context['input_tokens']==capture['input_tokens']
            parsed=strict_body_capture(tokenizer,capture['token_ids'],tokenizer.eos_token_id)
            assert all(capture[k]==v for k,v in parsed.items())
            assert 1<=len(capture['token_ids'])<=192
            assert capture['actual_forwarded_tokens']==len(ids)+len(capture['token_ids'])-int(capture['ended_at_eos'])
            verified.append(dict(id=q['id'],arm=arm,capture_sha256=digest(capture),exact_cpu_context_match=True))
    result=dict(status='pass',source_snapshots=len(launch['source_files']),frozen_files=len(frozen['files']),remote_hashes=len(hashes),cache_checks=40,capture_checks=42,note_check=check,captures=verified,training_performed=False)
    (RUN/'source-capture-verification.json').write_bytes(canonical(result))
    print(json.dumps({k:v for k,v in result.items() if k!='captures'}))
if __name__=='__main__':main()
