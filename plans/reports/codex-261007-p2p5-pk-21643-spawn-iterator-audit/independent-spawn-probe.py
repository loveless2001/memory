"""CPU-only review probe: actual spawn functions, generator-shaped Dict fakes, no remote writes."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
SLOTS = ("learned-n16", "learned-n32", "single_cell-n16", "single_cell-n32", "random_fixed-n16",
         "random_fixed-n32", "oracle-n32", "memory_off-n16", "memory_off-n32")
FILES = {
    "slot": ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py",
    "readings": ROOT / "modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py",
}
sources = {kind: path.read_text() for kind, path in FILES.items()}
for kind, source in sources.items():
    (OUT / f"reviewed-{kind}-runner.py").write_text(source)


class GeneratorDict(dict):
    def keys(self):
        yield from dict.keys(self)

    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


class IteratorFailure(GeneratorDict):
    def keys(self):
        # RPC failure occurs during iteration rather than at keys() call time.
        if False:
            yield None
        raise RuntimeError("injected streaming Dict RPC failure")


def probe(kind, slot, guard_kind, variant="current"):
    path, source = FILES[kind], sources[kind]
    old = "if any(True for _ in guard.keys()):"
    assert source.count(old) == 1
    if variant == "old_len":
        source = source.replace(old, "if len(guard.keys()):")
    elif variant == "none_sentinel":
        source = source.replace(old, "if next(iter(guard.keys()), None) is not None:")
    os.environ["M4_PK_SLOT"] = slot
    m = {"__name__": "independent_review", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), m)
    guard = IteratorFailure() if guard_kind == "rpc_error" else GeneratorDict()
    keys = {"used": "app_id", "none": None, "false": False, "zero": 0, "empty_string": ""}
    if guard_kind in keys:
        guard[keys[guard_kind]] = "prior-value"
    control = GeneratorDict(app_id="ap-controller", price_sha256=m["file_sha"](m["PRICE_FILE"]), deadline_epoch=2e10)
    dicts = {m["CONTROL_GUARD_DICT"]: control, m["GUARD_DICT"]: guard}
    calls = []
    m["modal"] = types.SimpleNamespace(
        Dict=types.SimpleNamespace(from_name=lambda name, **kw: dicts.setdefault(name, GeneratorDict())),
        App=types.SimpleNamespace(lookup=lambda name: types.SimpleNamespace(
            app_id="ap-controller" if name == m["CONTROL_APP_NAME"] else "ap-target")),
        Function=types.SimpleNamespace(from_name=lambda *args: types.SimpleNamespace(
            spawn=lambda *args: calls.append(args) or types.SimpleNamespace(object_id="fc-review-only"))),
    )
    m["subprocess"] = types.SimpleNamespace(run=lambda *args, **kw: types.SimpleNamespace(stdout=""))
    m["app_state"] = lambda app_id: "deployed"
    m["time"] = types.SimpleNamespace(time=lambda: 1_000_000.0)
    if kind == "readings":
        m["slots_ready"] = lambda local: None
    with tempfile.TemporaryDirectory(prefix="pk-iterator-review-") as temp:
        m["LOCAL_OUT"] = temp
        root = Path(temp) / m["GROUP"] / (slot if kind == "slot" else "readings")
        error = None
        try:
            m["spawn"]()
        except (SystemExit, RuntimeError, TypeError) as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        reg = dicts.get(m["CONTROL_REGISTRY_DICT"], {})
        result = {"kind": kind, "slot": slot, "guard": guard_kind, "variant": variant,
                  "error": error, "calls": len(calls), "root_exists": root.exists(),
                  "registered": m["APP_NAME"] in reg}
        if variant == "current":
            if guard_kind == "empty":
                assert error is None and len(calls) == 1 and root.is_dir() and result["registered"], result
                prov = json.loads((root / "launch_provenance.json").read_text())
                assert prov["deadline_epoch"] == guard["deadline_epoch"] == reg[m["APP_NAME"]]["deadline_epoch"]
                assert prov["deployed_app_id"] == guard["app_id"] == reg[m["APP_NAME"]]["app_id"] == "ap-target"
                assert json.loads((root / "call.json").read_text())["call_id"] == "fc-review-only"
            else:
                assert error is not None and not calls and not root.exists() and not result["registered"], result
                assert error["type"] == ("RuntimeError" if guard_kind == "rpc_error" else "SystemExit"), result
        elif variant == "old_len":
            assert error and error["type"] == "TypeError" and not calls and not root.exists(), result
        else:
            assert error is None and len(calls) == 1 and result["registered"], result
        return result


rows = []
for kind, slots in (("slot", SLOTS), ("readings", ("learned-n32",))):
    for slot in slots:
        for guard_kind in ("empty", "used", "none", "false", "zero", "empty_string", "rpc_error"):
            rows.append(probe(kind, slot, guard_kind))
        rows.append(probe(kind, slot, "empty", "old_len"))
        rows.append(probe(kind, slot, "none", "none_sentinel"))
out = {"status": "PASS", "current_cases": 70, "negative_mutation_cases": 20,
       "runner_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sources.items()},
       "remote_writes": 0, "results": rows}
(OUT / "independent-spawn-probe.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "results"}))
