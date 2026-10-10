"""Candidate inventory audit: existing-object reads/exports and local hashes only; no deletion."""
import ast
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import modal

ROOT=Path('/home/lenovo/projects/memory')
OUT=Path(__file__).parent
OLD=ROOT/'plans/reports/codex-261010-gravity-22360-closing-cleanup-review'
B3=ROOT/'plans/reports/codex-261010-gravity-wait55-b3-terminal-audit'
summary={'utc_start':datetime.now(timezone.utc).isoformat(),'errors':{},'remote_mutations':0,'compute_dispatches':0,'local_deletions':0}
def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,default=str)+'\n')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def cli(*args):
    proc=subprocess.run([sys.executable,'-m','modal',*args,'--json'],text=True,capture_output=True,timeout=60)
    proc.check_returncode()
    return json.loads(proc.stdout)

apps=cli('app','list'); containers=cli('container','list')
save('apps-live.json',apps);save('containers-live.json',containers)
assert all(r['state']=='stopped' and str(r['tasks'])=='0' for r in apps)
assert not containers
summary['shutdown']='stopped_verified'

# Extract only the pure encoder/decoder definitions from the prior reviewed exporter.
tree=ast.parse((OLD/'capture-readonly.py').read_text())
helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'encode','decode'}]
ns={'base64':base64}
exec(compile(ast.Module(body=helpers,type_ignores=[]),'<prior-export-codec>','exec'),ns)
encode,decode=ns['encode'],ns['decode']
prior_exports={r['name']:r for r in json.loads((OLD/'q4-export-index.json').read_text())}
names=json.loads((OLD/'q4-name-whitelist.json').read_text())
assert len(names)==38 and set(names)==set(prior_exports)
names=sorted(names+['m4-sgm-p2p5-b3-shift2-fill-long-starts-v1'])
assert len(names)==len(set(names))==39
save('q4-name-whitelist.json',names)
dict_rows=cli('dict','list');save('dicts-live.json',dict_rows)
live_names={r['name'] for r in dict_rows if 'p2p5' in r['name']}
assert set(names)==live_names, {'unexpected':sorted(live_names-set(names)),'missing':sorted(set(names)-live_names)}
(OUT/'q4-dicts').mkdir(exist_ok=True)
def export(name):
    d=modal.Dict.from_name(name,create_if_missing=False)
    raw=list(d.items())
    items=[{'key':encode(k),'value':encode(v)} for k,v in raw]
    assert all((decode(x['key']),decode(x['value']))==old for x,old in zip(items,raw))
    doc={'name':name,'object_id':d.object_id,'format':'typed-json-kv-v1','entry_count':len(items),'items':items}
    dest=OUT/'q4-dicts'/f'{name}.json'
    dest.write_text(json.dumps(doc,indent=2)+'\n')
    old_match=None
    if name in prior_exports:
        old=OLD/'q4-dicts'/f'{name}.json'
        assert sha(old)==prior_exports[name]['sha256'], name
        prior=json.loads(old.read_text())
        old_match=d.object_id==prior['object_id'] and items==prior['items']
        assert old_match, 'old Dict changed: '+name
    else:
        raw_dict=dict(raw)
        assert raw_dict==json.loads((B3/'live-snapshot.json').read_text())['dict']
    return {'name':name,'object_id':d.object_id,'entry_count':len(items),'sha256':sha(dest),'matches_prior_export':old_match,'round_trip':'PASS'}
with ThreadPoolExecutor(max_workers=4) as pool:
    exports=list(pool.map(export,names))
save('q4-export-index.json',exports)
summary['Q4']={'dicts':len(exports),'entries':sum(x['entry_count'] for x in exports),'original38_unchanged':True,'b3_exported':True}

def volume_audit(key,name,root,expected):
    vol=modal.Volume.from_name(name,create_if_missing=False)
    def listing():
        return sorted([{'path':e.path.lstrip('/'),'size':e.size,'type':e.type.name,'mtime':e.mtime} for e in vol.iterdir('/',recursive=True)],key=lambda e:e['path'])
    before=listing()
    files={x['path']:x for x in before if x['type']=='FILE'}
    assert set(files)==set(expected), (key,sorted(set(files)^set(expected)))
    verified=[]
    for rel in sorted(files):
        local=root/rel
        assert local.is_file() and local.stat().st_size==files[rel]['size']==expected[rel]['bytes'] and sha(local)==expected[rel]['sha256'],rel
        h=hashlib.sha256();n=0
        for chunk in vol.read_file('/'+rel):
            h.update(chunk);n+=len(chunk)
        assert n==files[rel]['size'] and h.hexdigest()==expected[rel]['sha256'],rel
        verified.append({'path':rel,'bytes':n,'sha256':h.hexdigest(),'retained_path':str(local),'remote_local_match':True})
    after=listing()
    assert before==after,'Volume changed during read: '+name
    save(f'{key.lower()}-live-list.json',before)
    save(f'{key.lower()}-verified-files.json',verified)
    return {'volume':name,'files':len(verified),'bytes':sum(x['bytes'] for x in verified),'listing_stable':True,'remote_local_all_hashes_match':True}
q3_rows=json.loads((OLD/'q3-file-verification.json').read_text())
q3={x['path'].lstrip('/'):{'bytes':x['size'],'sha256':x['sha256']} for x in q3_rows}
b3_rows=json.loads((B3/'live-snapshot.json').read_text())['files']
q5={'b3-run-v1/'+x['path']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in b3_rows}
# The B3 mirror root has no campaign directory component; use a mapping-specific root.
q5={'/'.join(k.split('/')[1:]):v for k,v in q5.items()}
def b3_audit():
    vol=modal.Volume.from_name('memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1',create_if_missing=False)
    before=sorted([{'path':e.path.lstrip('/'),'size':e.size,'type':e.type.name,'mtime':e.mtime} for e in vol.iterdir('/',recursive=True)],key=lambda e:e['path'])
    files={x['path'].removeprefix('b3-run-v1/'):x for x in before if x['type']=='FILE'}
    assert all(x['path'].startswith('b3-run-v1/') for x in before if x['type']=='FILE') and set(files)==set(q5)
    result=[]
    for rel in sorted(files):
        local=B3/'volume'/rel
        assert sha(local)==q5[rel]['sha256'] and local.stat().st_size==q5[rel]['bytes']==files[rel]['size']
        h=hashlib.sha256();n=0
        for c in vol.read_file('/'+files[rel]['path']):h.update(c);n+=len(c)
        assert h.hexdigest()==q5[rel]['sha256'] and n==files[rel]['size']
        result.append({'path':files[rel]['path'],'bytes':n,'sha256':h.hexdigest(),'retained_path':str(local),'remote_local_match':True})
    after=sorted([{'path':e.path.lstrip('/'),'size':e.size,'type':e.type.name,'mtime':e.mtime} for e in vol.iterdir('/',recursive=True)],key=lambda e:e['path'])
    assert before==after
    save('q5-live-list.json',before);save('q5-verified-files.json',result)
    return {'volume':'memsub-m4-sgm-p2p5-b3-shift2-fill-long-v1','files':len(result),'bytes':sum(x['bytes'] for x in result),'listing_stable':True,'remote_local_all_hashes_match':True}
with ThreadPoolExecutor(max_workers=2) as pool:
    f3=pool.submit(volume_audit,'Q3','memsub-m4-sgm-p2p5-b2-occupied-fill-long-v1',OLD/'q3-complete-volume',q3)
    f5=pool.submit(b3_audit)
    summary['Q3']=f3.result();summary['Q5']=f5.result()

temps=[]
for p in sorted(Path('/tmp').glob('b3-mut-*')):
    st=p.lstat()
    assert stat.S_ISDIR(st.st_mode) and st.st_uid==os.getuid() and not p.is_symlink(),str(p)
    total=0;files=0;links=[]
    for cur,dirs,fnames in os.walk(p,followlinks=False):
        for n in dirs+fnames:
            q=Path(cur)/n;s=q.lstat()
            if stat.S_ISLNK(s.st_mode):links.append({'path':str(q.relative_to(p)),'target':os.readlink(q)})
            if stat.S_ISREG(s.st_mode):total+=s.st_size;files+=1
    temps.append({'path':str(p),'dev':st.st_dev,'inode':st.st_ino,'uid':st.st_uid,'regular_file_bytes':total,'regular_files':files,'symlinks':links})
save('q7-path-whitelist.json',[x['path'] for x in temps]);save('q7-inventory.json',temps)
in_use=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        links=[os.readlink(proc/'cwd')]
        for fd in (proc/'fd').iterdir():
            try:links.append(os.readlink(fd))
            except OSError:pass
        matched=sorted({p['path'] for p in temps for target in links if target==p['path'] or target.startswith(p['path']+'/')})
        if matched:in_use.append({'pid':int(proc.name),'paths':matched})
    except (OSError,PermissionError):continue
save('q7-in-use.json',in_use)
summary['Q7']={'directories':len(temps),'regular_file_bytes':sum(t['regular_file_bytes'] for t in temps),'symlink_entries':sum(len(t['symlinks']) for t in temps),'processes_using_paths':in_use}
summary['utc_done']=datetime.now(timezone.utc).isoformat()
save('summary.json',summary)
print(json.dumps(summary,indent=2))
