"""Audit source identity and exact normalized-turn overlap without semantic claims."""
import json,hashlib
from collections import defaultdict
from pathlib import Path
from experiments.context_policy.preflight import canonical,digest
from experiments.context_policy.personamem import reader_history,normalized
PLAN=Path(__file__).resolve().parent;ROOT=PLAN.parents[2];DATA=PLAN.parent/'20260910-v2-broader-eval-data'
def read(p):return json.loads(p.read_text())
def main():
    selection=read(PLAN/'selection.json');new=read(DATA/'histories.json')
    assert set(new)=={r['persona_id'] for r in selection['selected']}
    assert not set(new)&set(selection['excluded_acquired']+selection['excluded_reserved'])
    manifests=read(DATA/'source-manifest.json')['files']
    for r in manifests:
        p=ROOT/r['local_path'];raw=p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['sha256']
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['oid']
        assert reader_history(read(p))==new[r['persona_id']]
    old={}
    for pid in selection['excluded_acquired']:
        paths=list((ROOT/'data/context-policy/personamem-v2/data/chat_history_32k').glob('*_persona'+pid+'.json'))
        assert len(paths)==1
        old[pid]=reader_history(read(paths[0]))
    rawhash={digest(h):pid for pid,h in old.items()}
    assert not any(digest(h) in rawhash for h in new.values())
    turns=defaultdict(list)
    for kind,group in [('new',new),('prior',old)]:
        for pid,h in group.items():
            for i,m in enumerate(h):
                key=digest(dict(role=m['role'],content=normalized(m['content'])))
                turns[key].append(dict(group=kind,persona_id=pid,turn=i,role=m['role']))
    shared=[];parent={pid:pid for pid in new};all_parent={kind+':'+pid:kind+':'+pid for kind,g in [('new',new),('prior',old)] for pid in g}
    def all_find(x):
        while all_parent[x]!=x:all_parent[x]=all_parent[all_parent[x]];x=all_parent[x]
        return x
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    for sha,entries in turns.items():
        unique={(e['group'],e['persona_id']) for e in entries}
        all_keys=[group+':'+pid for group,pid in unique]
        for key in all_keys[1:]:all_parent[all_find(key)]=all_find(all_keys[0])
        if len(unique)<2 or not any(e['group']=='new' for e in entries):continue
        shared.append(dict(normalized_turn_sha256=sha,occurrences=entries))
        pids=list({e['persona_id'] for e in entries if e['group']=='new'})
        for pid in pids[1:]:parent[find(pid)]=find(pids[0])
    components=defaultdict(list)
    for pid in new:components[find(pid)].append(pid)
    all_components=defaultdict(list)
    for key in all_parent:all_components[all_find(key)].append(key)
    relevant_components=[v for v in all_components.values() if any(k.startswith('new:') for k in v)]
    cross=[s for s in shared if any(e['group']=='prior' for e in s['occurrences'])]
    result=dict(status='source_audit_complete',selected_families=20,prior_families=len(old),exact_history_overlap=0,persona_overlap=0,
        shared_normalized_turns=len(shared),shared_turns_with_prior=len(cross),new_exact_turn_components=list(components.values()),
        source_component_count=len(components),all_source_components_with_new=relevant_components,all_source_components_with_new_count=len(relevant_components),shared_turn_details=shared,semantic_near_duplicate_audit=False,
        limitation='Exact normalized-turn links only. Different personas do not guarantee independent content; templates and paraphrases are not excluded.',training_allowed=False)
    (DATA/'source-overlap-audit.json').write_bytes(canonical(result))
    print(json.dumps({k:v for k,v in result.items() if k!='shared_turn_details'}))
if __name__=='__main__':main()
