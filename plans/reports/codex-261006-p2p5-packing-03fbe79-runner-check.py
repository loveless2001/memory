"""Local failure/dispatch fixtures for the packing dev runner; no Modal invocation."""
import ast
import hashlib
import importlib.util
import io
import json
import signal
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
REL = "modal-runners/modal-m4-sgm-p2p5-dev-gpu-test-runner.py"
OUT = ROOT / "plans/reports/codex-261006-p2p5-packing-03fbe79-runner-check.json"


def main():
    source = (ROOT / REL).read_bytes()
    assert source == subprocess.check_output(["git", "show", "03fbe79:"+REL],cwd=ROOT)
    old = ast.parse(subprocess.check_output(["git", "show", "1306f26:"+REL],cwd=ROOT))
    new = ast.parse(source)
    old_fun = next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=="run_remote")
    new_fun = next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=="_run_body")
    assert [ast.dump(n,include_attributes=False) for n in old_fun.body] == [ast.dump(n,include_attributes=False) for n in new_fun.body]
    spec = importlib.util.spec_from_file_location("codex_packing_dev_runner", ROOT / REL)
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    assert run.run_remote.spec.cpu == (4.0,4.0) and run.run_remote.spec.memory == (32768,32768)
    assert run.run_remote_a100_80gb.spec.cpu == (8.0,8.0) and run.run_remote_a100_80gb.spec.memory == (65536,65536)
    resource = {"l40s":{"cpu":run.run_remote.spec.cpu,"memory_mib":run.run_remote.spec.memory},
                "a100-80gb":{"cpu":run.run_remote_a100_80gb.spec.cpu,"memory_mib":run.run_remote_a100_80gb.spec.memory}}
    run.app = SimpleNamespace(app_id="fixture-no-remote-app")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer,mode="w:gz"):
        pass
    fixtures = []
    with tempfile.TemporaryDirectory(prefix="codex-packing-runner-") as tmp:
        for gpu in ("l40s","a100-80gb"):
            for case in ("ok","rc7","timeout","remote_error","bad_archive","sigterm"):
                calls = []

                def remote(*args):
                    calls.append({"gpu":gpu,"args":args})
                    if case=="remote_error":
                        raise RuntimeError("fixture remote error")
                    if case=="sigterm":
                        signal.raise_signal(signal.SIGTERM)
                    return {"returncode":7 if case=="rc7" else "timeout" if case=="timeout" else 0,
                            "wall_s":1.0,"tar":b"bad" if case=="bad_archive" else buffer.getvalue()}

                def wrong(*args):
                    raise AssertionError("wrong GPU function dispatched")

                run.run_remote = SimpleNamespace(remote=remote if gpu=="l40s" else wrong)
                run.run_remote_a100_80gb = SimpleNamespace(remote=remote if gpu=="a100-80gb" else wrong)
                old_signal = signal.getsignal(signal.SIGTERM)
                dest = Path(tmp)/(gpu+"-"+case)
                error = None
                try:
                    run.main(script="fixture.py",out=str(dest),gpu=gpu)
                except BaseException as exc:
                    error = {"type":type(exc).__name__,"text":str(exc)}
                finally:
                    signal.signal(signal.SIGTERM,old_signal)
                meta = json.loads((dest/"run.json").read_text())
                assert len(calls)==1 and (error is None)==(case=="ok")
                assert meta["gpu"] == ("L40S" if gpu=="l40s" else "A100-80GB")
                assert meta["outcome"] == ("ok" if case=="ok" else "child failed" if case in ("rc7","timeout") else "remote call failed")
                assert "client_wall_s" in meta
                fixtures.append({"gpu":gpu,"case":case,"error":error,"manifest":meta,"mock_remote_calls":len(calls)})
    nominal = 1440*(D('.000694')+8*D('.0000131')+64*D('.00000222'))
    conservative = 1440*(D('.000694')+2*(8*D('.0000131')+64*D('.00000222')))
    total = conservative+D('.168384')+D('.10')
    assert total < D(2)
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"source_commit":"03fbe79",
        "runner_sha256":hashlib.sha256(source).hexdigest(),"remote_operations":False,"paid_work":False,
        "resource_fields":resource,"shared_body_identical_to_1306f26":True,"fixtures":fixtures,
        "reservation":{"nominal_runtime_usd":str(nominal),"twice_cpu_ram_runtime_usd":str(conservative),
            "build_usd":"0.168384","margin_usd":"0.10","total_usd":str(total),"booked_usd":"1.98","cap_usd":"2.00",
            "basis":"1320s attached outer client + 120s detection/teardown; latter includes kill escalation",
            "limits":"Overuse/teardown/build allowances are assumptions, not a platform spending guarantee. Crash restarts are possible even with retries=0; no operator retry approved.",
            "rates_source":"https://modal.com/pricing"},"packing_measurement_clearance":False}
    OUT.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"runner_fixtures_passed":len(fixtures),"reservation_total_usd":str(total),
        "runner_sha256":report["runner_sha256"],"packing_measurement_clearance":False},indent=2))


if __name__ == "__main__":
    main()
