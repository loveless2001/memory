"""Local prelaunch integrity checks. No model loading or remote execution."""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.context_policy.broader_protocol import validate_span, render_spans, SYSTEM
from experiments.context_policy.broader_notes import ledger_for
from experiments.context_policy.repair_pilot import validate_bundle
from experiments.context_policy.preflight import canonical, digest
from prepare import HERE, V2, read, file_hash, runtime_sources


def require(test, message):
    if not test: raise ValueError(message)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    protected=read(HERE/'protected-inputs.json')
    for path,sha in protected.items():require(file_hash(ROOT/path)==sha,'protected input changed: '+path)
    bundle=read(HERE/'reader-input.json');validate_bundle(bundle)
    require(bundle==read(V2/'reader-bundle.json'),'reviewed reader inputs changed')
    worklist=read(HERE/'note-worklist.json');views=read(HERE/'reader-views.json');schedule=read(HERE/'schedule.json')
    require(len(worklist)==60 and {w['history_id'] for w in worklist}==set(bundle['histories']),'worklist coverage')
    seen=set()
    for w in worklist:
        history=bundle['histories'][w['history_id']]
        require(w['history_sha256']==digest(history),'worklist source binding')
        if w['parent_history_id']:
            require(w['parent_history_id'] in seen,'parent note not prepared before branch')
            base=bundle['histories'][w['parent_history_id']]
            require(history[:len(base)]==base and len(history)==len(base)+2,'branch prefix changed')
        seen.add(w['history_id'])
    require(len(bundle['questions'])==120 and len(views)==120,'question coverage')
    require([q['id'] for q in bundle['questions']]==[s['id'] for s in schedule],'schedule alignment')
    require(all(sorted(s['round_order'])==[0,1,2] for s in schedule),'round coverage')
    require(file_hash(HERE/'reader-views.json')==read(HERE/'query-only-selection.json')['reader_view_sha256'],'evidence changed after reference-free selection')
    source_slices=0
    for q in bundle['questions']:
        v=views[q['id']];history=bundle['histories'][q['persona_id']]
        require(set(v)=={'history_sha256','query_sha256','recent','retrievals'},'private fields in view')
        require(v['history_sha256']==digest(history) and v['query_sha256']==digest(q['query']),'view binding')
        require(len(v['retrievals'])==2,'retrieval round count')
        for i,part in enumerate([v['recent']]+v['retrievals']):
            require(set(part)=={'spans','text','tokens'},'private view part fields')
            for span in part['spans']:validate_span(history,span);source_slices+=1
            expected=render_spans(part['spans']) or ('No additional matching dialogue was found.' if i else '')
            require(part['text']==expected,'rendered source changed')
            require(part['tokens'] <= (512 if i==0 else 1024),'reported source budget exceeded')
    cpu=read(HERE/'cpu-report.json')
    require(cpu['status']=='CPU_PASS' and not cpu['detector_misses'],'CPU preflight has unresolved failures')
    require(cpu['system_sha256']==digest(SYSTEM),'system changed after CPU checks')
    require(cpu['prompt_checks']==360 and cpu['append_prefix_checks']==240,'CPU prompt coverage')
    require(cpu['base_note_updates']==131 and cpu['branch_note_updates']==40,'note workload changed')
    require(read(HERE/'test-results.json')['exit_code']==0,'targeted tests did not pass')
    freeze=HERE/'freeze.json'
    if args.freeze:
        require(not freeze.exists(),'refusing to overwrite preflight freeze')
        sources=runtime_sources()
        (HERE/'runtime-sources.json').write_bytes(canonical(sources))
        files={str(p.relative_to(ROOT)):file_hash(p) for p in sorted(HERE.rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts and p.name not in ('freeze.json','verification.json')}
        files.update(sources)
        for path in ('modal-runners/modal-broader-reader.py','tests/test_context_policy_broader_protocol.py'):
            files[path]=file_hash(ROOT/path)
        freeze.write_bytes(canonical({'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'files':files,'gpu_execution_authorized_by_this_file':False,'planned_gpu_seconds':2400,
            'reader_inputs':['reader-input.json','reader-views.json','note-worklist.json','schedule.json','runtime-config.json']}))
    require(freeze.exists(),'preflight not frozen')
    manifest=read(freeze)
    for path,sha in manifest['files'].items():require(file_hash(ROOT/path)==sha,'prelaunch file changed: '+path)
    require(runtime_sources()==read(HERE/'runtime-sources.json'),'runtime source closure mismatch')
    result={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS',
        'freeze_sha256':file_hash(freeze),'prelaunch_files_verified':len(manifest['files']),
        'protected_prior_files_verified':len(protected),'source_slices_verified':source_slices,
        'note_updates':171,'planned_captures':360,'gpu_gate':'not_run','reader_inference':'not_run',
        'scope':'CPU preparation; real model cache, notes and answer validation remain runtime gates'}
    (HERE/'verification.json').write_bytes(canonical(result))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
