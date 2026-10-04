"""Prepare opaque case/answer IDs without previous author judgments or scores."""
import json,hashlib,datetime
from pathlib import Path
from experiments.context_policy.preflight import canonical,digest
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
DATA=BASE.parent/'20260910-v2-withdrawal-regression-data'
RUN=BASE.parent/'20260910-v2-withdrawal-regression'
def read(p):return json.loads(p.read_text())
def main():
    packet=BASE/'packet';assert not packet.exists();packet.mkdir()
    bundle=read(DATA/'reader-input.json');refs={r['id']:r for r in map(json.loads,(DATA/'references.jsonl').read_text().splitlines())}
    captures=read(RUN/'artifacts/captures.json')
    histories=sorted(bundle['histories'],key=lambda pid:digest('judge-history-v1:'+pid))
    history_ids={pid:f'H{i+1:03d}' for i,pid in enumerate(histories)}
    for pid,hid in history_ids.items():
        out=packet/'histories'/f'{hid}.json';out.parent.mkdir(exist_ok=True)
        out.write_bytes(canonical(dict(history_id=hid,turns=[dict(turn=i,**m) for i,m in enumerate(bundle['histories'][pid])],history_sha256=digest(bundle['histories'][pid]))))
    queries=sorted(bundle['questions'],key=lambda q:digest('judge-case-v1:'+q['id']))
    sealed=[];index=[];templates=[]
    for i,q in enumerate(queries):
        cid=f'C{i+1:03d}';hid=history_ids[q['persona_id']];ref=refs[q['id']]
        proposal={k:ref[k] for k in ('answer','personal_claims','constraints','mode')}
        record=dict(case_id=cid,history_id=hid,history_file=f'../histories/{hid}.json',history_sha256=digest(bundle['histories'][q['persona_id']]),question=q['query']['content'],proposed_reference=proposal,proposal_sha256=digest(proposal))
        out=packet/'references'/f'{cid}.json';out.parent.mkdir(exist_ok=True);out.write_bytes(canonical(record))
        group=sorted([c for c in captures if c['id']==q['id']],key=lambda c:digest('judge-answer-v1:'+digest(c)))
        answers=[];binding=dict(case_id=cid,original_id=q['id'],reference_sha256=digest(ref),answers=[])
        for j,c in enumerate(group):
            aid=f'{cid}-{chr(65+j)}'
            shown=dict(answer_id=aid,text=c['text'],actual_messages=c['messages'],ended_at_eos=c['ended_at_eos'],collection_mode=c['collection_mode'],supplied_prefix=c['supplied_prefix'])
            shown['shown_answer_sha256']=digest(shown)
            answers.append(shown);binding['answers'].append(dict(answer_id=aid,arm=c['arm'],capture_sha256=digest(c),shown_answer_sha256=shown['shown_answer_sha256']))
        out=packet/'answers'/f'{cid}.json';out.parent.mkdir(exist_ok=True);out.write_bytes(canonical(dict(case_id=cid,answers=answers)))
        sealed.append(binding);index.append(dict(case_id=cid,history_id=hid,reference_file=f'references/{cid}.json',answer_file=f'answers/{cid}.json'))
        templates.append(dict(case_id=cid,reference_verdict=None,reference_reason='',reference_evidence=[],reference_revision_if_needed=None,answers=[dict(answer_id=a['answer_id'],task_complete=None,source_consistent=None,supported_in_visible_state=None,withdrawal_compliant=None,ownership_correct=None,body_valid=None,within_90_words=None,verdict=None,reason='',evidence=[]) for a in answers]))
    (packet/'index.json').write_bytes(canonical(index))
    (BASE/'sealed-map.json').write_bytes(canonical(sealed))
    (BASE/'review-template.json').write_bytes(canonical(dict(reviewer_model='',reviewer_version='',reviewed_at='',prior_verdicts_seen=False,blinding_notes='',cases=templates)))
    source_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),DATA/'reader-input.json',DATA/'references.jsonl',RUN/'artifacts/captures.json']}
    manifest=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),cases=21,answers=42,histories=18,previous_verdicts_in_packet=False,source_files=source_files,packet_files={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(packet.rglob('*.json'))},sealed_map_sha256=hashlib.sha256((BASE/'sealed-map.json').read_bytes()).hexdigest(),template_sha256=hashlib.sha256((BASE/'review-template.json').read_bytes()).hexdigest())
    (BASE/'packet-manifest.json').write_bytes(canonical(manifest))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('source_files','packet_files')}))
if __name__=='__main__':main()
