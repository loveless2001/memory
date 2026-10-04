"""Select new source families using IDs/paths only, before inspecting dialogue."""
import csv,json,hashlib,datetime,re
from pathlib import Path
from experiments.context_policy.preflight import canonical,digest
from experiments.context_policy.personamem import REVISION,TRAIN_SHA256,history_path
ROOT=Path(__file__).resolve().parents[3]
PLAN=Path(__file__).resolve().parent
SOURCE=ROOT/'data/context-policy/personamem-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert sha(SOURCE/'benchmark/text/train.csv')==TRAIN_SHA256
    paths={}
    with (SOURCE/'benchmark/text/train.csv').open() as f:
        for row in csv.DictReader(f):
            pid=row['persona_id'];path=str(history_path(row['chat_history_32k_link']))
            if pid in paths:assert paths[pid]==path
            paths[pid]=path
    old=json.loads((PLAN.parent/'20260910-v2-personamem-intake/structure-audit.json').read_text())
    split=old['candidate_persona_split']
    reserved=set(split['train']+split['validation']+split['internal_test'])
    acquired={re.search(r'_persona(\d+)\.json$',p.name).group(1) for p in (SOURCE/'data/chat_history_32k').glob('*.json')}
    remaining=set(paths)-reserved-acquired
    selected=sorted(remaining,key=lambda pid:hashlib.sha256(('context-policy-broader-eval-v1:'+pid).encode()).hexdigest())[:20]
    tree={x['path']:x for x in json.loads((SOURCE/'history-tree.json').read_text())}
    rows=[]
    for pid in selected:
        rows.append(dict(persona_id=pid,path=paths[pid]))
    result=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),revision=REVISION,source_dataset='bowen-upenn/PersonaMem-v2',selection_seed='context-policy-broader-eval-v1:',selected=rows,excluded_acquired=sorted(acquired,key=int),excluded_reserved=sorted(reserved,key=int),eligible=len(remaining),target_histories=20,raw_bytes_estimate=4_000_000,source_text_inspected=False,official_external_test=False,
        files={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),PLAN/'PLAN.md',SOURCE/'benchmark/text/train.csv',SOURCE/'history-tree.json',PLAN.parent/'20260910-v2-personamem-intake/structure-audit.json']})
    out=PLAN/'selection.json';assert not out.exists();out.write_bytes(canonical(result))
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','excluded_reserved','selected')}));print('selected',selected)
if __name__=='__main__':main()
