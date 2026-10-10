"""Finalize the original c3c6fa2 audit only after its independent CPU suite exits."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PLAN = ROOT / "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe"
package = json.loads((OUT / "package-and-import-evidence.json").read_text())
suite = json.loads((OUT / "independent-sgm-suite-resumed-exit.json").read_text())
suite_text = (OUT / "independent-sgm-suite-resumed.txt").read_text()
registry = json.loads((OUT / "independent-real-cpu-registry-resumed.json").read_text())
registry_exit = json.loads((OUT / "independent-real-cpu-registry-resumed-exit.json").read_text())
smoke = json.loads((OUT / "smoke-boundary-evidence.json").read_text())
assert suite["rc"] == 0 and "557 passed, 2 skipped" in suite_text
assert registry_exit["rc"] == 0 and registry["all_equal"]
assert all(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == item["expected"]
           for rel, item in package["hashes"].items())
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == package["head"]
assert not subprocess.check_output(["git", "diff", "--name-only", "13d6fe5", "fbfebe0", "--", "memsub",
                                    "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"], cwd=ROOT, text=True).strip()

result = {
    "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
    "chat_request": [21758, 21779],
    "code_commit": subprocess.check_output(["git", "rev-parse", "fbfebe0"], cwd=ROOT, text=True).strip(),
    "package_commit": package["head"],
    "verdict": "HOLD: implementation clearance and local GPU smoke withheld",
    "findings": [
        {"priority": "P1", "file": "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py",
         "line": 49, "title": "Build-stage module import lacks sibling slot logic",
         "evidence": "package-and-import-evidence.json",
         "required_fix": "Supply the dependency before run_function or isolate the builder; verify the effective builder files offline."},
        {"priority": "P2", "file": "scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py",
         "line": 15, "title": "Documented outer timeout exceeds the 3600-second whole-process limit",
         "evidence": "smoke-boundary-evidence.json",
         "required_fix": "Retain an executable outer hard KILL/3600 process-group boundary and a harmless termination regression."},
    ],
    "independent_cpu_suite": {"rc": suite["rc"], "summary": suite_text.strip().splitlines()[-1],
                              "wall_s": suite["wall_s"]},
    "real_cpu_registry": registry,
    "package_files_sha256_verified": package["package_files"],
    "registry_schema_rederive_equal": package["registry_schema_rederive_equal"],
    "saved_mutation_evidence": {"aimed_tests_caught": 26, "independently_rerun": False,
                                "note": "Private-copy driver, re-freeze procedure, aimed failures, baseline and stored hashes inspected."},
    "ledger_decimal": package["ledger_decimal"],
    "scope": {"pretrained_qwen_forward_passes": 0, "gpu_smokes": 0, "modal_rpc_or_build_deploy_spawn": False,
              "shared_implementation_modified": False},
    "authorization": "User 21755 conditional go is retained for the scoped two-cell probe at 40.75 USD; unresolved gates remain.",
    "next_gate": "Review the corrected frozen implementation and evidence, then the single bounded local smoke; no paid launch yet."
}
(OUT / "review-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
review = f"""Independent review of chat 21758, requested by user 21779

Verdict: HOLD. Implementation clearance and the local GPU smoke are withheld.
Code: {result['code_commit']}; evidence package: {result['package_commit']}.

P1 - Build-stage import failure
modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py:28-31,49,55
Installed Modal 1.5.1 defines _build_environment as a nonserialized FILE function.
Its effective source mounts contain only the runner, and its base image has no
local mount layers. Importing that file loads the sibling slot-logic module before
the builder is callable. The sibling is absent, producing FileNotFoundError.
The later final-image add_local_file cannot satisfy an earlier build stage.
The offline negative control uses only SDK-declared builder files; adding the
sibling gives a passing import. No build or network call was used to establish this.
Fix the build-stage file set and add an effective-stage import regression.

P2 - Smoke launch does not enforce its outer 3600-second limit
scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py:15,27-28,66,86-88
The documented command times out after 3660 seconds with a further 30-second kill
grace. The inner 3600-second Watchdog starts in main after imports and is cancelled
before writing the summary. The proposal requires an OUTER hard whole-process
3600-second bound through cleanup. Use a KILL/3600 process-group launcher, retain
the inner watchdog and worker parent-death handling, and test a harmless process
tree. Pin the regression to the scoped 20 updates, rather than <=50.

Independent checks completed
- All 24 package hashes match; code/config/test bytes are unchanged between the
  implementation and package commits. Registry and schema equal their derivation.
- CPU sgm suite plus artifact hygiene: {result['independent_cpu_suite']['summary']}; exit 0.
- Real CPU construction of both Qwen cells: frozen registry equality, 46 tensors
  each, head [64,512]; exit 0. Construction only, with no pretrained forward pass.
- The validator retains the original non-schema checks and enforces the exact
  grad_norm null contract in COMPLETE, collect and reading. Tiny CPU graph,
  residual control and supervisor subprocess paths are covered by the suite.
- Reaper decisions reject invalid deadlines, bind stop IDs, quarantine mismatches
  and retain abandonment handling. Four total admitted starts and one immutable
  31946.2-second slot deadline remain unchanged. These local checks do not prove
  remote scheduling or stop latency.
- Saved private-copy mutation evidence: baseline 65/65 and 26/26 aimed failures,
  with re-freezing inspected and hashes verified. The 26 mutation runs were not
  independently repeated in this review.
- Decimal ledger: GPU 38.229480912 USD; reaper 0.1738677348333333333333333333;
  images 0.336768; margin 2; total 40.74011664683333333333333333 <= 40.75.
  This remains conditional on its declared rate, period and stop-tail assumptions;
  local tests do not establish a provider-level guaranteed cost ceiling.
- The reading uses the frozen comparator hashes, episode pairing and existing
  P2D/P2G criteria; failed/invalid cells remain unavailable and claims exploratory.
- memsub and the historical campaign files are unchanged by the implementation.
  The two coherent modules exceeding the 200-line guideline are not blockers.

Disposition and boundaries
Claude accepted both findings in 21785 and is preparing fixes in a private worktree.
This review does not certify those proposed fixes. Re-freeze the corrected source
and package with the two new regressions, then obtain implementation clearance
before the one seed-7, batch-2, 20-update, 3600-second local smoke with no retry.
The existing user 21755 conditional go is retained for the two-cell 40.75 USD scope;
it does not close implementation, smoke-evidence or launch-provenance gates.
No new permission is requested by this review. No GPU smoke, Modal RPC, build,
deploy or spawn was performed. Shared implementation files were not modified.
Earlier incomplete independent logs were retained; only the completed resumed
suite and registry outputs above are claimed as independent verification.
"""
(OUT / "review.txt").write_text(review)
names = ["review.txt", "review-evidence.json", "check-package.py", "package-and-import-evidence.json",
         "check-smoke-boundary.py", "smoke-boundary-evidence.json", "finalize-review.py",
         "independent-sgm-suite-resumed.txt", "independent-sgm-suite-resumed-exit.json",
         "independent-real-cpu-registry-resumed.json", "independent-real-cpu-registry-resumed.log",
         "independent-real-cpu-registry-resumed-exit.json", "suite-command.json"]
(OUT / "SHA256SUMS-audit.txt").write_text("".join(
    f"{hashlib.sha256((OUT / name).read_bytes()).hexdigest()}  {name}\n" for name in names))
print(json.dumps({"verdict": result["verdict"], "suite": result["independent_cpu_suite"],
                  "review": str(OUT / "review.txt")}, indent=2))
