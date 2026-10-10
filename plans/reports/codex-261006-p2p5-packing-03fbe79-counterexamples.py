"""CPU-only adversarial probes of the actual packing result aggregator; no training."""
import json
import subprocess
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
rel = "scripts/sgm-p2p5-gpu-packing-concurrent-training-throughput-test.py"
mod = types.ModuleType("packing_probe")
mod.__file__ = str(ROOT / rel)
source = subprocess.check_output(["git", "show", f"03fbe79:{rel}"], cwd=ROOT)
exec(compile(source, mod.__file__, "exec"), mod.__dict__)


class Finished:
    def __init__(self, *a, **kw):
        pass

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


def probe(label, spans, means):
    with tempfile.TemporaryDirectory(prefix="codex-packing-probe-") as tmp:
        out = Path(tmp)
        d = out / "p2-k2"
        d.mkdir()
        for rank, (span, mean) in enumerate(zip(spans, means)):
            worker = {"phase":2,"rank":rank,"k":2,"seed":99+rank,
                      "measured_start":span[0],"measured_end":span[1],
                      "mean_measured_s":mean,"peak_allocated_bytes":1,
                      "updates":[{"update":i,"seconds":mean,"t_end":span[0]+(i-1)*mean,
                                  **({"barrier_release":span[0]-mean} if i==0 else {})}
                                 for i in range(8)]}
            (d / f"worker-{rank}.json").write_text(json.dumps(worker))
        with patch.object(mod.subprocess, "Popen", Finished):
            actual = mod.run_test(2, 2, out)
        wall_rate = 12 / (max(s[1] for s in spans)-min(s[0] for s in spans))
        return {"case":label,"actual_status":actual["status"],"actual_overlap_s":actual["overlap_s"],
                "actual_rate":actual["aggregate_updates_per_s"],"fixed_work_wall_rate":wall_rate,
                "inflation_ratio":actual["aggregate_updates_per_s"]/wall_rate}


results = [probe("disjoint measurement windows",[(0,6),(20,26)],[1,1]),
           probe("unequal lengths with early worker finish",[(0,.6),(0,60)],[.1,10])]
out = ROOT / "plans/reports/codex-261006-p2p5-packing-03fbe79-counterexamples.json"
out.write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps(results,indent=2))
