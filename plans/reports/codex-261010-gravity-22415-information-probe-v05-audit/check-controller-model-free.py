"""Execute a copy of the controller with only its cd changed, using fake stage/validator programs.
No systemd scope, timeout process, probe runtime, model or numerical profile is executed.
"""
import json
import os
import pathlib
import subprocess

OUT = pathlib.Path(__file__).resolve().parent
REL = "plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe"
SOURCE = OUT / "sources-94d85af" / REL / "run-probe-chain-s1-s2-full.sh"
cases = ["success", "s1_fail", "s1_validation_fail", "s2_fail", "s2_validation_fail",
         "admission_fail", "full_fail", "full_validation_fail", "existing_dir", "existing_exit"]
fake = '''#!/usr/bin/python3
import json,os,pathlib,sys
a=sys.argv[1:]; case=os.environ["CHAIN_CASE"]; p=pathlib.Path.cwd()
kind=pathlib.Path(sys.argv[0]).name
with open(p/"calls.jsonl", "a") as f: f.write(json.dumps({"kind":kind,"args":a})+"\\n")
if kind == "systemd-run":
    mode=a[a.index("--mode")+1]; out=pathlib.Path(a[a.index("--out")+1]); out.mkdir()
    sys.exit(137 if case == mode+"_fail" else 0)
if "--full-wall" in a:
    if case == "admission_fail": sys.exit(1)
    print(1234); sys.exit(0)
mode=a[a.index("--validate")+1]
sys.exit(1 if case == mode+"_validation_fail" else 0)
'''
results=[]
for case in cases:
    root=OUT/"controller-fixtures"/case
    d=root/REL; d.mkdir(parents=True)
    binpath=root/"fakebin"; binpath.mkdir()
    venv=root/".venv/bin"; venv.mkdir(parents=True)
    for p in (binpath/"systemd-run", venv/"python"):
        p.write_text(fake); p.chmod(0o700)
    if case == "existing_dir": (d/"s1-smoke").mkdir()
    if case == "existing_exit": (d/"s1-smoke.exit").write_text("137\n")
    source=SOURCE.read_text()
    assert source.count("cd /home/lenovo/projects/memory || exit 2") == 1
    script=root/"controller.sh"
    script.write_text(source.replace("cd /home/lenovo/projects/memory || exit 2", f"cd {root} || exit 2"))
    env={**os.environ,"CHAIN_CASE":case,"PATH":str(binpath)+":"+os.environ["PATH"],"PKPROBE_FORBID_MODEL":"1"}
    r=subprocess.run(["bash",str(script)],env=env,text=True,capture_output=True,timeout=15)
    calls=[json.loads(x) for x in (root/"calls.jsonl").read_text().splitlines()] if (root/"calls.jsonl").exists() else []
    stages=[x["args"][x["args"].index("--mode")+1] for x in calls if x["kind"]=="systemd-run"]
    expect=(["s1","s2","full"] if case in ("success","full_fail","full_validation_fail") else
            ["s1","s2"] if case in ("s2_fail","s2_validation_fail","admission_fail") else
            [] if case in ("existing_dir","existing_exit") else ["s1"])
    if case in ("success", "full_validation_fail"):
        final=calls[-1]["args"]
        assert "--s1" in final and "--s2" in final and final[final.index("--validate")+1]=="full"
    state=(d/"chain-status.txt").read_text().strip()
    assert stages==expect, (case,stages,expect)
    assert (r.returncode==0)==(case=="success"), (case,r.returncode)
    assert (state=="COMPLETE")==(case=="success")
    for c in (x for x in calls if x["kind"]=="systemd-run"):
        assert "MemoryMax=4400M" in c["args"] and "MemorySwapMax=1200M" in c["args"]
        assert "--signal=KILL" in c["args"]
    results.append({"case":case,"exit":r.returncode,"stages":stages,"state":state,"calls":calls})
(OUT/"controller-checks.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps({"cases_passed":len(results),"real_stages_executed":0}))
