"""Reviewer-owned rev2 probes: local CPU, private variants and faked Modal only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).resolve().parent
OUT = REPORT / "probes-v2"
OUT.mkdir()
REV = "89df08fd08e238936902bb764a2928ac7b9f30b4"
PLAN = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
INDEX = ROOT / PLAN / "pk-prep/gate3-rev2/SHA256SUMS-gate3-package-rev2.txt"
TREE = OUT / "private-tree"
TREE.mkdir()
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, TREE / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

checks = {}
for line in INDEX.read_text().splitlines():
    want, rel = line.split("  ", 1)
    if want == "memsub_source_tree_sha256":
        continue
    checks[rel] = sha(ROOT / rel) == want
    p = TREE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(subprocess.check_output(["git", "show", f"{REV}:{rel}"], cwd=ROOT))
for rel in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", REV, "memsub"], cwd=ROOT, text=True).splitlines():
    p = TREE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(subprocess.check_output(["git", "show", f"{REV}:{rel}"], cwd=ROOT))
sys.path.insert(0, str(TREE))
os.environ["M4_PK_SLOT"] = "learned-n32"
rd = load("scripts/sgm-p2p5-pk-campaign-readings.py", "independent_rd")
cp = load("modal-runners/modal-m4-sgm-p2p5-pk-control-plane-reaper-logic.py", "independent_cp")
slot = load("modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py", "independent_slot")
reader = load("modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py", "independent_reader")
shared = load("modal-runners/modal-m4-sgm-p2p5-reaper-lifetime-stop-logic.py", "independent_shared")
memsub = rd.source_tree_sha256(TREE / "memsub")
checks["memsub_source_tree_sha256"] = memsub == "2eee4228124e9d292ed4079476ca276e8ce8f9ac7c8d83d44bcd51333687a19b"
assert all(checks.values())
result = {"revision": REV, "index_sha256": sha(INDEX), "index_checks": checks, "no_remote_calls": True}
assert cp.launch_manifest_problem(TREE) is None
assert rd.binding_problem(rd.current_identity()) is None
result["manifest_clean"] = {"analysis_closure": sorted(rd.analysis_closure()), "launch_verified": True}
assert len(rd.analysis_closure()) == 7

# Preserve fixed protocol/model/proof bytes from the audited revision.
protected = [f"{PLAN}/prereg.md", f"{PLAN}/prereg-amendment-pk-packed-a100-resume.md",
             "configs/m4_sgm_p2p5_grid.json", f"{PLAN}/pk6/priced-estimate-v5.json"]
result["protected_inputs_unchanged"] = {
    rel: (ROOT / rel).read_bytes() == subprocess.check_output(["git", "show", f"f8d8592:{rel}"], cwd=ROOT)
    for rel in protected}
proof = ROOT / PLAN / "p2p5-pk-proof-v1"
proof_checks = {}
for line in (proof / "SHA256SUMS-volume-evidence.txt").read_text().splitlines():
    h, rel = line.split("  ", 1)
    if rel.endswith("/run_manifest.json"):
        proof_checks[rel] = sha(proof / rel) == h
assert all(result["protected_inputs_unchanged"].values()) and len(proof_checks) == 10 and all(proof_checks.values())
result["proof_manifests"] = {"count": len(proof_checks), "unchanged": all(proof_checks.values())}

# R2: real changed decision semantics, with unchanged expected identity, must refuse before evidence access.
dep = TREE / "scripts/sgm-p2p5-decision-rules.py"
original = dep.read_bytes()
expected = rd.current_identity()
try:
    assert b"INTERFACE_MIN = 0.50" in original
    dep.write_bytes(original.replace(b"INTERFACE_MIN = 0.50", b"INTERFACE_MIN = 0.99"))
    changed = load("scripts/sgm-p2p5-pk-campaign-readings.py", "independent_changed_rd")
    touched = []
    with patch.object(changed, "bind_cells", side_effect=lambda *a: touched.append("bind")), \
         patch.object(changed, "reserved_rows", side_effect=lambda *a: touched.append("reserved")):
        rep = changed.readings(OUT, {}, expected, OUT / "dependency-mutation-output")
    assert changed.DR.INTERFACE_MIN == .99 and touched == []
    assert all(v["reading"].startswith("unavailable") for v in rep["n"].values())
    assert cp.launch_manifest_problem(TREE) is not None
    result["dependency_mutation"] = {"threshold": changed.DR.INTERFACE_MIN, "accesses": touched,
                                     "unavailable": rep["unavailable"]}
finally:
    dep.write_bytes(original)

pilots = rd.expand_cells(json.loads(rd.GRID.read_text()))
params = OUT / "synthetic-checkpoint"
params.mkdir()
checkpoint = params / "trained_parameters.safetensors"
checkpoint.write_bytes(b"private synthetic parameter bytes")
def rows(arm, ivs, oracle_ok):
    out = []
    for iv in ivs:
        for b in range(16):
            for e in range(16):
                ix = b * 16 + e
                ok = oracle_ok if arm == "oracle" else (ix % 10 < 9 if arm == "learned" else ix % 10 == 0)
                ok = ok and iv == "none"
                for q in range(4):
                    label = (ix + q) % 64
                    out.append(dict(batch=b, episode=e, episode_hash=f"h{b}-{e}", query=q, key=q,
                                    label=label, pred=label if ok else (label+1)%64, correct=ok, intervention=iv))
    return out
def scenario(label, oracle_ok, mutate_checkpoint=False):
    calls = []
    def reserved(cid, path, pilot, n, ivs, dest):
        calls.append([pilot["arm"], n, pilot["seed"], list(ivs)])
        rr = rows(pilot["arm"], ivs, oracle_ok[n])
        if mutate_checkpoint and len(calls) == 6:
            checkpoint.write_bytes(checkpoint.read_bytes() + b" changed")
        return rr, {"rows_sha256": "synthetic", "accuracy_none":
                    sum(rd.P2D.episode_scores(rr, "none").values()) / rd.P2D.N_EPISODES}
    with patch.object(rd, "bind_cells", return_value=({c:params for c in pilots}, None)), \
         patch.object(rd, "parity", return_value=None), patch.object(rd, "reserved_rows", side_effect=reserved):
        rep = rd.readings(OUT, {}, rd.current_identity(), OUT / label)
    assert [c[:3] for c in calls[:4]] == [["oracle",32,0],["oracle",32,1],["oracle",16,0],["oracle",16,1]]
    assert all(c[3] == ["none","bank_derange","read_offset"] for c in calls[:4])
    assert all(a == "oracle" or oracle_ok[n] for a,n,_s,_ivs in calls)
    if mutate_checkpoint:
        assert all(v["reading"].startswith("unavailable") for v in rep["n"].values())
    else:
        assert rep["end_binding"] == "verified"
    return {"calls": calls, "readings": {n:v["reading"] for n,v in rep["n"].items()}, "end_binding":rep["end_binding"]}
result["oracle_order_and_gating"] = {
    "both_pass": scenario("both-pass", {32:True,16:True}),
    "n32_fail": scenario("n32-fail", {32:False,16:True}),
    "n16_fail": scenario("n16-fail", {32:True,16:False}),
    "both_fail": scenario("both-fail", {32:False,16:False})}
result["checkpoint_end_mutation"] = scenario("checkpoint-end-mutation", {32:True,16:True}, True)

# R3: actual collectors refuse malformed provenance before poll/stop/verify/fetch.
def never(*a, **k):
    raise AssertionError("side effect reached before provenance validation")
refusals = {}
for name,m,leaf in [("slot",slot,slot.SLOT),("readings",reader,"readings")]:
    m.LOCAL_OUT = str(OUT / f"collector-{name}")
    root = Path(m.LOCAL_OUT) / m.GROUP / leaf
    root.mkdir(parents=True)
    refused = []
    for bad in [None,"","  ",5,"MISSING"]:
        prov = {"slot":slot.SLOT,"deployed_app_id":bad,"deadline_epoch":100.,"expected_identity":{"memsub":memsub}}
        if bad == "MISSING":
            del prov["deployed_app_id"]
        (root / "launch_provenance.json").write_text(json.dumps(prov))
        kwargs = dict(poller=never,stopper=never,verifier=never,fetch=never,now=500.)
        if name == "slot":
            kwargs["export"] = never
        try:
            m.collect(**kwargs)
        except SystemExit as e:
            assert "no bound app id" in str(e)
            refused.append(bad)
        else:
            raise AssertionError("malformed app id accepted")
    refusals[name] = refused
result["collector_bad_id_refusals"] = refusals
import modal
import modal.experimental
stops,lookups = [],[]
def lookup(name, **kw):
    lookups.append([name,kw])
    return SimpleNamespace(app_id="ap-replacement")
with patch.object(modal.App,"lookup",side_effect=lookup), \
     patch.object(modal.experimental,"stop_app",side_effect=lambda *a,**k:stops.append(a)):
    try:
        cp.strict_stop(shared.stop_bound_app,"app","ap-old")
    except RuntimeError:
        pass
    else:
        raise AssertionError("replaced app accepted")
assert len(lookups)==1 and stops==[]
result["replacement_id_stop"] = {"lookups":lookups,"stops":stops}

# R4: exercise production _real_collect verifier closures, not a replacement verdict.
verification = {}
for name,m in [("slot",slot),("readings",reader)]:
    cases = {}
    for label,apps,conts,want in [
        ("seven_tasks",[{"app_id":"ap-bound","state":"stopped","tasks":"7"}],[],False),
        ("remaining_container",[{"app_id":"ap-bound","state":"stopped","tasks":"0"}],
                               [{"app_id":"ap-bound","container_id":"ta-1"}],False),
        ("stopped_zero",[{"app_id":"ap-bound","state":"stopped","tasks":"0"}],[],True),
        ("unlisted_zero",[],[],True)]:
        queries=[]
        def cli(args):
            queries.append(args)
            return apps if args[0]=="app" else conts
        def inspect(**deps):
            return deps["verifier"]("ap-bound")
        with patch.object(m,"load_cp",return_value=cp),patch.object(cp,"modal_cli_json",side_effect=cli), \
             patch.object(m,"collect",side_effect=inspect):
            v=m._real_collect()
        assert v["verified"] is want and queries==[["app","list"],["container","list"]]
        cases[label]=v
    verification[name]=cases
result["real_collector_verification"] = verification

# R5: a malformed co-tenant record, fresh snapshot failures, and durable pre-fetch shutdown evidence.
from memsub.sgm import packed_slot_epoch_state as es
slot.LOCAL_OUT=str(OUT / "cell-collection")
croot=Path(slot.LOCAL_OUT)/slot.GROUP/slot.SLOT
croot.mkdir(parents=True)
(croot/"launch_provenance.json").write_text(json.dumps({"slot":slot.SLOT,"deployed_app_id":"ap-bound",
    "deadline_epoch":100.,"expected_identity":{"memsub":memsub}}))
remote=OUT/"synthetic-remote"/slot.SLOT/"cells"
cells=slot.slot_cells(json.loads((TREE/slot.GRID_FILE).read_text()))
for cid,pilot in cells.items():
    cdir=remote/cid
    rec=es.inherit(cdir,1,[1],{"memsub":memsub},1500)
    rec["chain"],rec["state"]=[{"epoch":1,"g":30,"step":1500,"file":"x","sha256":"y"}],es.TRAINED
    es.mark(rec,es.COMPLETE,outputs={"attempt":f"cells/{cid}/epoch-1/attempt-1","files":{}})
    es.write_record(cdir,rec)
badcid=sorted(cells)[0]
(remote/badcid/"epoch-1/state.json").write_text("{broken")
with patch.object(slot,"GRID_FILE",str(TREE/slot.GRID_FILE)),patch.object(slot,"REGISTRY_FILE",str(TREE/slot.REGISTRY_FILE)), \
     patch.object(slot,"SCHEMA_FILE",str(TREE/slot.SCHEMA_FILE)):
    def fetch(dest):
        saved=json.loads((croot/"collect_status.json").read_text())
        assert saved["final_shutdown"]["status"]=="stopped_verified"
        shutil.copytree(remote.parents[1],dest)
        return {"returncode":0}
    kwargs=dict(poller=lambda c:("result",None),stopper=lambda *a:None,verifier=lambda i:{"verified":True},
                fetch=fetch,export=lambda r:{"admission":{"start-1":1}},now=500.,validate=lambda *a:None)
    rep=slot.collect(**kwargs)
    assert rep["cells"][badcid]["state"]=="INVALID"
    assert rep["cells"][sorted(cells)[1]]["state"]=="COMPLETE"
    result["malformed_cell_containment"]=rep
    validated=[]
    def failed_fetch(dest):
        dest.mkdir(parents=True)
        return {"returncode":1}
    rep2=slot.collect(**{**kwargs,"fetch":failed_fetch,"validate":lambda *a:validated.append(1)})
    assert all(v["state"]=="UNAVAILABLE" for v in rep2["cells"].values()) and validated==[]
    assert (croot/"volume-evidence/collect-2").exists()
    result["failed_fetch_containment"]=rep2

# Pure arithmetic reproduction and separate summation; no paid execution.
published=json.loads((ROOT/PLAN/"pk6/priced-estimate-v6.json").read_text())
fresh=json.loads((REPORT/"independent-priced-estimate-v6.json").read_text())
oldhead=published["inputs"].pop("git_head")
newhead=fresh["inputs"].pop("git_head")
assert published==fresh
assert fresh["readings"]["counts"]=={"checkpoint_builds":38,"parity_cells":18,"reserved_populations":20,
                                      "telemetry_dev_batches":64}
# Published components are rounded separately to 0.1 s; sum using the rounding error bound.
rounding_delta=sum(fresh["readings"]["items_s"].values())-fresh["readings"]["life_s"]
assert abs(rounding_delta)<=.05*(len(fresh["readings"]["items_s"])+1)
reserve=fresh["planning_reserve_per_app_envelope"]
assert abs(sum(v for k,v in reserve.items() if k!="total_usd")-reserve["total_usd"])<1e-10
result["price_reproduction"]={"same_except_git_head":True,"published_git_head":oldhead,"fresh_git_head":newhead,
    "estimate_usd":fresh["estimate"]["usd"],"reserve_usd":reserve["total_usd"],"counts":fresh["readings"]["counts"],
    "rounded_component_delta_s":rounding_delta}
assert cp.launch_manifest_problem(TREE) is None
assert subprocess.run(["git","diff","--exit-code","HEAD","--","memsub","scripts","modal-runners","configs","tests"],cwd=ROOT).returncode==0
(OUT/"independent-probes.json").write_text(json.dumps(result,indent=2,default=str)+"\n")
print(json.dumps({"pass":True,"index_sha256":result["index_sha256"],"focused_probes":"R1-R6","price":result["price_reproduction"]},indent=2))
