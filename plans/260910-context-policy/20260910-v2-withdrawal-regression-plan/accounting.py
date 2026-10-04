"""Read the completed app's measured billing; no execution or resubmission."""
import asyncio
import datetime
import json
from pathlib import Path
from modal.client import _Client
from modal_proto import api_pb2
from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp

RUN = Path(__file__).resolve().parent.parent / '20260910-v2-withdrawal-regression'


async def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    app_id = json.loads((RUN / 'launch.json').read_text())['app_id']
    client = await _Client.from_env()
    request = api_pb2.WorkspaceBillingReportRequest(
        start_timestamp=Timestamp(seconds=int((now-datetime.timedelta(days=1)).timestamp())),
        end_timestamp=Timestamp(seconds=int((now+datetime.timedelta(hours=1)).timestamp())),
        resolution='h', app_ids=[app_id])
    rows = [MessageToDict(row, preserving_proto_field_name=True)
            async for row in client.stub.WorkspaceBillingReport.unary_stream(request)]
    result = dict(observed_at=now.isoformat(), app_id=app_id, rows=rows)
    (RUN / 'billing.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__': asyncio.run(main())
