"""Inspect the frozen smoke launcher boundary; no GPU, model load, or subprocess launch."""
import ast
import hashlib
import json
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
path = ROOT / "scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py"
src = path.read_text()
tree = ast.parse(src)
command = next(line.strip() for line in ast.get_docstring(tree).splitlines()
               if line.strip().startswith("timeout "))
args = shlex.split(command)
outer_seconds = float(args[2])
kill_grace_seconds = float(args[1].split("=", 1)[1])
main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
watchdog = next(n for n in ast.walk(main) if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "Watchdog")
cancel = next(n for n in ast.walk(main) if isinstance(n, ast.Call)
              and ast.unparse(n.func) == "wd.cancel")
summary_write = next(n for n in ast.walk(main) if isinstance(n, ast.Call)
                     and "smoke-summary.json" in ast.unparse(n.func))
assert outer_seconds == 3660 and kill_grace_seconds == 30
assert cancel.lineno < summary_write.lineno
evidence = {
    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "documented_command": command,
    "required_outer_hard_limit_s": 3600,
    "documented_outer_timeout_s": outer_seconds,
    "documented_kill_grace_s": kill_grace_seconds,
    "worst_case_outer_forced_kill_s": outer_seconds + kill_grace_seconds,
    "watchdog_armed_in_main_line": watchdog.lineno,
    "watchdog_cancelled_line": cancel.lineno,
    "summary_write_line": summary_write.lineno,
    "whole_process_3600_s_bound_established": False,
    "note": "Imports precede main; the inner timer is cancelled before summary writing."
}
(OUT / "smoke-boundary-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps(evidence, indent=2))
