"""Independent Decimal audit of committed snapshots; no remote billing/API calls."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
PLAN=ROOT/'plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen'
PKG=PLAN/'pk-campaign-terminal'
ATT=PLAN/'pk-campaign-launch/attempt-2'
COMMIT='13d6fe5'
inputs,checks={},{}

def read(p):
    p=Path(p)
    b=p.read_bytes()
    inputs[str(p.relative_to(ROOT))]=hashlib.sha256(b).hexdigest()
    return b

def load(p):return json.loads(read(p),parse_float=Decimal)

def check(name,ok):
    checks[name]=bool(ok)
    assert ok,name

def frozen(p):
    return subprocess.check_output(['git','show',COMMIT+':'+str(p.relative_to(ROOT))],cwd=ROOT)

p1=ATT/'94-billing-hourly-prelim-20261007T1744Z.json'
p2=ATT/'97-billing-hourly-prelim-snapshot-2-20261007T1915Z.json'
s1,s2=load(p1),load(p2)
check('snapshot2 frozen bytes',read(p2)==frozen(p2))
stderr=ATT/'97-billing-prelim-snapshot-2.stderr'
check('stderr empty and frozen',read(stderr)==b'' and frozen(stderr)==b'')
for line in read(PKG/'SHA256SUMS-terminal-package.txt').decode().splitlines():
    sha,name=line.split(None,1)
    p=PKG/name
    check('metadata sha '+name,hashlib.sha256(read(p)).hexdigest()==sha)
    check('metadata frozen '+name,read(p)==frozen(p))

baseline=load(ROOT/'plans/reports/codex-261007-p2p5-pk-21652-launch-verification/launch-verification.json')
slot_ids={s['provenance']['deployed_app_id'] for s in baseline['slots'].values()}
read_id='ap-MvPw7JVom3vnRTxVVyzldN'
c2='ap-suOdTgdc8PNSfZ3jbnsesa'
c1='ap-eqwdT119XvSoBJC1I2kDqC'
known=slot_ids|{read_id,c2,c1}
check('nine known slots',len(slot_ids)==9)

def campaign(rows):
    selected,excluded=[],[]
    for r in rows:
        cost=Decimal(r['cost'])
        assert cost.is_finite() and cost>=0
        if r['description'].startswith('memsub-m4-sgm-p2p5-pk-campaign'):
            assert r['object_id'] in known and r['environment']=='main'
            assert '2026-10-07T00:00:00'<=r['interval_start']<='2026-10-07T17:00:00'
            selected.append(r)
        else:excluded.append(r)
    sums=defaultdict(Decimal)
    for r in selected:sums[r['object_id']]+=Decimal(r['cost'])
    return selected,excluded,dict(sums)

a,ax,sa=campaign(s1)
b,bx,sb=campaign(s2)
check('all known campaign apps covered',set(sa)==set(sb)==known)
check('slot subtotal unchanged',sum((sb[k] for k in slot_ids),Decimal(0))==Decimal('119.27095429'))
for k in slot_ids|{read_id,c1}:
    check('app rows unchanged '+k,[r for r in a if r['object_id']==k]==[r for r in b if r['object_id']==k])
check('readings exact',sb[read_id]==Decimal('7.08987892'))
check('attempt1 controller exact',sb[c1]==Decimal('0.00004958'))
check('controller2 old exact',sa[c2]==Decimal('0.08021808'))
check('controller2 new exact',sb[c2]==Decimal('0.08107773'))
old,new=sum(sa.values(),Decimal(0)),sum(sb.values(),Decimal(0))
check('old total exact',old==Decimal('126.44110087'))
check('new total exact',new==Decimal('126.44196052'))
check('delta entirely controller',new-old==sb[c2]-sa[c2]==Decimal('0.00085965'))

def index(rows):
    indexed={(r['object_id'],r['environment'],r['interval_start']):r for r in rows}
    assert len(indexed)==len(rows)
    return indexed

ia,ib=index(a),index(b)
check('campaign hour keys unchanged',set(ia)==set(ib))
changed=[k for k in ia if ia[k]!=ib[k]]
check('one changed campaign row',changed==[(c2,'main','2026-10-07T17:00:00')])
check('unrelated puzzle excluded',all(r['object_id']=='ap-Pu6Dy71P8DakYgOma6JC0A' for r in ax+bx))
doc=read(PKG/'terminal-package.md').decode()
check('document snapshot and status',all(x in doc for x in ['126.44196052','0.00085965','PRELIMINARY',
      'hourly backfill','unattributed attempt-1 image','separate $8.57 proof hold']))
check('snapshot2 doc sha',inputs[str(p2.relative_to(ROOT))].startswith('7b26bad17f61'))
read(Path(__file__))
result={'status':'PASS: saved-snapshot arithmetic and package integrity only; billing PRELIMINARY',
        'owner_commit':COMMIT,'checks':checks,'source_counts':[len(s1),len(s2)],
        'campaign_rows':[len(a),len(b)],'excluded_rows':[len(ax),len(bx)],
        'previous_usd':str(old),'snapshot2_usd':str(new),'delta_usd':str(new-old),
        'snapshot2_by_app_usd':{k:str(v) for k,v in sb.items()},
        'changed_campaign_row_keys':changed,'latest_campaign_hour':max(r['interval_start'] for r in b),
        'open':['later hourly backfill','unattributed attempt-1 image build','separate proof hold $8.57'],
        'inputs_sha256':dict(sorted(inputs.items())),
        'limits':['no live API/app-state check','fetch timestamp and rc reported by owner; raw snapshot has no embedded fetch provenance',
                  'probe implementation tests are not independently verified by this billing audit']}
(OUT/'evidence.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:result[k] for k in ['status','source_counts','campaign_rows','excluded_rows','previous_usd','snapshot2_usd','delta_usd','latest_campaign_hour']}))
