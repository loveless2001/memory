"""Retain the r2 byte-review disposition after the independently executed focused suite."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
package = json.loads((OUT / "package-evidence.json").read_text())
suite = json.loads((OUT / "independent-focused-suite-exit.json").read_text())
summary = (OUT / "independent-focused-suite.txt").read_text().strip().splitlines()[-1]
assert suite["rc"] == 0 and "73 passed" in summary
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == package["package_commit"]
assert all(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == value["expected"]
           for rel, value in package["hashes"].items())
result = {
    "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
    "chat_request": 21800,
    "package_commit": package["package_commit"],
    "code_commits": ["8b476fd", "51b333d"],
    "verdict": "PASS: r2 implementation gate; one bounded local smoke cleared",
    "prior_findings": {"P1_builder_import": "closed", "P2_smoke_outer_boundary": "closed"},
    "independent_tests": {"summary": summary, "rc": suite["rc"], "wall_s": suite["wall_s"]},
    "package_files_verified": 26,
    "saved_full_suite": {"summary": package["saved_suite"], "independently_repeated_in_r2_review": False},
    "saved_mutations": package["saved_mutations"],
    "cleared_smoke": {"number_of_attempts": 1, "seed": 7, "batch": 2, "steps": 20, "checkpoint_every": 10,
                      "outer_wall_s": 3600, "inner_watchdog_s": 3540, "automatic_retry": False,
                      "command": "timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py --out <new dir>"},
    "paid_launch_cleared": False,
    "existing_paid_authorization": "User 21755 conditional two-cell go at 40.75 USD retained; smoke-evidence gate still open.",
    "limitations": ["Offline builder/runtime import checks do not execute a Modal image build.",
                    "Short harmless-tree timeout test plus command guard establishes the local launch mechanism; no GPU smoke was run by this audit.",
                    "The ledger remains conditional on its declared billing and stop-tail assumptions."],
    "implementation_modified_by_auditor": False,
    "modal_rpc_build_deploy_spawn_by_auditor": False,
}
(OUT / "review-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
(OUT / "review.txt").write_text(f"""Independent byte review of chat 21800: corrected readout probe package r2

Verdict: PASS for the implementation gate at {package['package_commit']}.
Both findings in review 21787 are closed. One local smoke is cleared as scoped
below. Paid build/deploy/spawn remains uncleared pending its evidence review.

P1 builder import - CLOSED
The slot logic is baked with copy=True before run_function, so the builder's
FILE entrypoint can import its sibling. The final GPU image inherits that layer.
The independently executed tests obtain entrypoint/COPY/deferred mount sets from
installed Modal 1.5.1, import in a fresh isolated interpreter, and exclude final
mounts from the builder positive control. The entrypoint-only negative control
fails as expected. Both run_slot and reaper runtime stage imports pass.
This is offline import/package evidence, not an executed Modal image build.

P2 local smoke bound - CLOSED
The smoke requires exactly timeout --signal=KILL 3600 followed by its own argv
and verifies membership in the timeout parent's process group before repository
imports or output-directory creation. Its inner watchdog is 3540 seconds and is
armed before heavy imports. The 20-update scope and private populations are pinned.
Independent subprocess tests verify refusal of missing/wrong/wrapped bounds and
a detached group. A short harmless three-process tree under the same KILL form
terminates as a group. Worker Popen and parent-death safeguards are preserved.

Evidence checked
- Independently executed focused tests: {summary}, exit 0.
- All 26 r2 package hashes match. The retained source patch is byte-identical to
  the four changed/new runner, smoke and test files. Eleven r1 bound source files
  are unchanged. memsub, configs and the historical campaign files are unchanged.
- Saved full-suite evidence: {package['saved_suite']}, exit 0. Hashes verified;
  the full suite was not independently repeated during this r2 review. The r1
  full suite had already independently passed 557/2 before these scoped fixes.
- Saved private-copy mutation evidence: baseline 73 passed, 38/38 aimed failures,
  all re-freezes successful. The original 26 mutation definitions are unchanged.
  The first run's argv-tail survivor and failing exit are retained; the wrapped
  command case closes it in the final run. Mutation runs were inspected, not
  independently repeated by this audit.
- The registry, validator, lifecycle logic, ledger and reading are unchanged.
  The earlier real CPU registry construction and Decimal ledger audit therefore
  retain their scope. Ledger total 40.7401166468 USD <= 40.75, conditional on its
  declared assumptions. Four total starts and one 31946.2-second slot deadline
  remain the paid scope; these are not the local smoke's settings.

Cleared next action
Claude may run ONE local, zero-charge smoke: seed 7, batch 2, 20 updates, C=10,
using its own populations and a new output directory, without an automatic retry:

timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-readout-probe-local-gpu-smoke.py --out <new dir>

Retain the exact argv, interpreter/environment and source identities, timestamps,
exit status, summary, worker log/record, checkpoint and output hashes, and observed
grad_norm/update_norm null paths. Partial/failed evidence remains as-is. A failure
does not authorize another smoke or a schema allowance added after observation.
Return the evidence for independent smoke clearance before any paid step.
The existing conditional user go is retained; this review requests no new approval.

No GPU smoke, pretrained Qwen forward, Modal RPC/build/deploy/spawn, implementation
edit or commit was performed by this audit. The review is saved in local audit
files only; the shared implementation stayed frozen throughout the check.
""")
names = ["review.txt", "review-evidence.json", "check-package-r2.py", "package-evidence.json",
         "finalize-review-r2.py", "focused-command.json", "independent-focused-suite.txt",
         "independent-focused-suite-exit.json"]
(OUT / "SHA256SUMS-audit.txt").write_text("".join(
    f"{hashlib.sha256((OUT / name).read_bytes()).hexdigest()}  {name}\n" for name in names))
print(json.dumps({"verdict": result["verdict"], "tests": summary, "paid_launch_cleared": False}, indent=2))
