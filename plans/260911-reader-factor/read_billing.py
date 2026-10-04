"""Read observed billing for this diagnostic's single GPU app."""
import asyncio,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from modal.client import _Client
from modal_proto import api_pb2

HERE=Path(__file__).resolve().parent

async def main():
    if (HERE/'result-manifest.json').exists():raise RuntimeError('Preserve frozen billing snapshot')
    app_ids=[json.loads((HERE/'run/launch.json').read_text())['app_id']]
    client=await _Client.from_env();now=datetime.now(timezone.utc)
    request=api_pb2.WorkspaceBillingReportRequest(resolution='h',app_ids=app_ids)
    request.start_timestamp.FromDatetime(datetime(2026,9,11,tzinfo=timezone.utc))
    request.end_timestamp.FromDatetime(now.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1))
    rows=[]
    async for item in client.stub.WorkspaceBillingReport.unary_stream(request):
        assert item.object_id in app_ids
        rows.append({'app_id':item.object_id,'description':item.description,'interval':item.interval.ToJsonString(),
                     'cost':item.cost,'cost_by_resource':dict(item.cost_by_resource)})
    result={'observed_at':now.isoformat(),'requested_app_ids':app_ids,'rows':rows,
            'reported_total_usd':str(sum((Decimal(r['cost']) for r in rows),Decimal(0))) if rows else None,
            'apps_without_reported_row':[a for a in app_ids if not any(r['app_id']==a for r in rows)],
            'caveat':'Observed billing can lag terminal execution. No reported row does not establish zero cost.'}
    (HERE/'billing.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':asyncio.run(main())
