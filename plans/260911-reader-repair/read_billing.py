"""Read billing for this app only; no inference or account mutation."""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from pathlib import Path

from modal.client import _Client
from modal_proto import api_pb2

HERE = Path(__file__).resolve().parent / 'run'


async def main():
    app_id = json.loads((HERE / 'launch.json').read_text())['app_id']
    client = await _Client.from_env()
    now = datetime.now(timezone.utc)
    request = api_pb2.WorkspaceBillingReportRequest(resolution='h', app_ids=[app_id])
    request.start_timestamp.FromDatetime(datetime(2026, 9, 10, 20, tzinfo=timezone.utc))
    request.end_timestamp.FromDatetime(now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    rows = []
    async for item in client.stub.WorkspaceBillingReport.unary_stream(request):
        if item.object_id != app_id:
            raise ValueError('billing service returned an unrelated app')
        rows.append({'object_id': item.object_id, 'description': item.description,
                     'environment_name': item.environment_name, 'interval': item.interval.ToJsonString(),
                     'cost': item.cost, 'cost_by_resource': dict(item.cost_by_resource)})
    result = {'observed_at': now.isoformat(), 'app_id': app_id, 'rows': rows,
              'reported_total_usd': str(sum((Decimal(r['cost']) for r in rows), Decimal(0))) if rows else None,
              'caveat': 'Observed billing may lag terminal execution; empty rows do not establish zero cost.'}
    (HERE / 'billing.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
