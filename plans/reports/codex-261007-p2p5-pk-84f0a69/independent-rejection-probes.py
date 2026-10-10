"""CPU-only audit counterexamples on copies of independently generated proof evidence.

No original evidence/source is changed. A reported false acceptance is a defect,
not clearance. The baseline comes from the real-worker focused pytest run.
"""
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import torch
from safetensors.torch import load_file, save_file

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
PROOF = HERE / "pytest-tmp/proof0"
RUN = HERE / "rejection-probes-run2"  # preserve the initial run and its exception log


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


acc = module("audit_acc", ROOT / "scripts/sgm-p2p5-pk-packed-proof-acceptance-compare.py")
test_spec = module("audit_spec", ROOT / "tests/test_sgm_pk_packed_proof_acceptance_compare.py")
from memsub.sgm import packed_slot_epoch_state as es
from memsub.sgm.packed_slot_supervisor import SlotSupervisor, expand_cells
from memsub.sgm.p2d_launch_guard import Watchdog


def record(path, d):
    path.write_text(json.dumps(d, indent=2))


def clone(name):
    dest = RUN / name
    shutil.copytree(PROOF, dest)
    return dest


def completed(ev):
    for scenario in test_spec.TINY["scenarios"]:
        for cell in test_spec.TINY["scenarios"][scenario]["cells"]:
            m, r = acc.authority(ev / scenario / "cells" / cell)
            if r["state"] == es.COMPLETE:
                yield ev / scenario / r["outputs"]["attempt"] / "out", es.epoch_dir(ev / scenario / "cells" / cell, m) / "state.json", r


results = {"baseline": acc.evaluate(PROOF, test_spec.TINY)}
assert results["baseline"]["pass"]

# Relative comparisons alone do not enforce a preregistered complete schema.
ev = clone("joint-gradient-omission")
removed = None
for f in ev.rglob("proof-capture/u*.pt"):
    d = torch.load(f, map_location="cpu", weights_only=False)
    removed = removed or sorted(d["grads"])[0]
    d["grads"].pop(removed)
    torch.save(d, f)
results["joint_gradient_omission"] = {"removed_expected_name": removed, **acc.evaluate(ev, test_spec.TINY)}

ev = clone("joint-empty-scientific-payload")
for out, path, r in completed(ev):
    record(out / "metrics.json", {})
    (out / "per_example_results.jsonl").write_text("")
    (out / "routing_telemetry.jsonl").write_text("")
    save_file({}, str(out / "trained_parameters.safetensors"))
    # Rebind hashes so this is also a schema counterexample, not merely damaged files.
    r["outputs"]["files"] = {n: es.file_sha256(out / n) for n in r["outputs"]["files"]}
    record(path, r)
    record(out.parent / "done.json", {"outputs": r["outputs"]["files"]})
results["joint_empty_scientific_payload"] = acc.evaluate(ev, test_spec.TINY)

ev = clone("missing-checkpoint-generations")
for f in ev.rglob("gen-*-step*.pt"):
    f.unlink()  # Only this new audit scratch copy; original proof files are preserved.
results["missing_checkpoint_generations"] = acc.evaluate(ev, test_spec.TINY)

ev = clone("wrong-predecessor-binding")
for f in ev.rglob("state.json"):
    d = json.loads(f.read_text())
    if d["inherited_from"]:
        d["inherited_from"]["record_sha256"] = "0" * 64
        record(f, d)
results["wrong_predecessor_hash"] = acc.evaluate(ev, test_spec.TINY)

ev = clone("wrong-identity-same-container")
for f in ev.rglob("state.json"):
    d = json.loads(f.read_text())
    d["identity"] = {"memsub": "wrong-source", "runner": "wrong-runner"}
    d["provenance"] = {"container_id": "same-container-for-every-epoch", "admitted_at": 0.0}
    record(f, d)
results["wrong_identity_and_same_container"] = acc.evaluate(ev, test_spec.TINY)

# The actual supervisor's COMPLETE validation accepts an empty worker hash map.
empty = RUN / "empty-done-supervisor"
cfg = next(iter(expand_cells(test_spec.TINY).values()))
cell = "learned-n4-s99"
sup = SlotSupervisor(root=empty, cells={cell: cfg}, epoch=1, admitted=[1], identity=test_spec.ID,
                     checkpoint_every=2, eval_cfg=test_spec.TINY["eval"], commit=lambda: None, reload=lambda: None)
sup.acknowledge()
sup.records[cell]["state"] = es.TRAINED
att = sup.attempt_dir(cell)
att.mkdir(parents=True)
record(att / "done.json", {"outputs": {}})
sup.finish(cell, 0)
results["empty_done_published_state"] = sup.records[cell]["state"]

# Real resume consumer: advertised generation step4 contains a valid step2 state.
# All original B evidence is retained in an extra directory inside the scratch copy.
ev = clone("metadata-step4-payload-step2")
(ev / "B").rename(ev / "retained-original-B")
for cell in test_spec.TINY["scenarios"]["B"]["cells"]:
    shutil.copytree(PROOF / "B/cells" / cell / "epoch-1", ev / "B/cells" / cell / "epoch-1")
cdir = ev / "B/cells/learned-n4-s99"
p = es.epoch_dir(cdir, 1) / "state.json"
r = json.loads(p.read_text())
link = r["chain"][-1]
assert link["step"] == 4
old = next(l for l in r["chain"] if l["step"] == 2)
target = es.epoch_dir(cdir, 1) / link["file"]
target.write_bytes((es.epoch_dir(cdir, 1) / old["file"]).read_bytes())
link["sha256"] = es.file_sha256(target)
record(p, r)
cells_all = expand_cells(test_spec.TINY)
sup = SlotSupervisor(root=ev / "B", cells={c: cells_all[c] for c in test_spec.TINY["scenarios"]["B"]["cells"]},
                     epoch=2, admitted=[1, 2], identity=test_spec.ID, checkpoint_every=2,
                     eval_cfg=test_spec.TINY["eval"], commit=lambda: None, reload=lambda: None,
                     ack_timeout_s=90, proof_capture=True, poll_s=.01)
watchdog = Watchdog(120)
try:
    try:
        resumed = sup.run()
    except Exception as e:
        resumed = {"raised": type(e).__name__, "message": str(e)}
finally:
    watchdog.cancel()
new = es.read_record(cdir, 2)
results["metadata_step4_payload_step2"] = {"consumer_result": resumed,
    "advertised_resume_step": new["physical"]["resume_step"], "actual_checkpoint_payload_step": 2,
    "observed_optimizer_updates": sup.observed("learned-n4-s99")["observed_updates"],
    **acc.evaluate(ev, test_spec.TINY)}

assert results["joint_gradient_omission"]["pass"]
assert results["joint_empty_scientific_payload"]["pass"]
assert results["missing_checkpoint_generations"]["pass"]
assert results["wrong_predecessor_hash"]["pass"]
assert results["wrong_identity_and_same_container"]["pass"]
assert results["empty_done_published_state"] == es.COMPLETE
assert not results["metadata_step4_payload_step2"]["pass"]
assert "strictly increase" in results["metadata_step4_payload_step2"]["consumer_result"]["message"]
assert results["metadata_step4_payload_step2"]["observed_optimizer_updates"] == 2
results["audit_status"] = "BLOCKING_FALSE_ACCEPTANCES_REPRODUCED_CPU_ONLY"
with (HERE / "independent-rejection-probes-run2.json").open("x") as f:
    json.dump(results, f, indent=2)
    f.write("\n")
print(json.dumps({k: ({"pass": v["pass"]} if isinstance(v, dict) and "pass" in v else v)
                  for k, v in results.items()}, indent=2))
