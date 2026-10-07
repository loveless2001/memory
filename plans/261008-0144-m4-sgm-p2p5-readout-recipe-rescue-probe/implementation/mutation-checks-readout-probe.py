"""Readout probe mutation checks on PRIVATE COPIES (codex 21648 discipline: the shared tree is only read).

For each mutation: copy the repo subset into a fresh scratch dir and undo ONE safeguard there. If the mutated file
feeds a frozen artifact (validator/freeze -> registry+schema, ledger script -> ledger), RE-FREEZE it inside the copy,
so the drift test cannot be what catches it. Then run the two probe test files in the copy, and require the AIMED
test among the failures. A baseline copy (no mutation) must pass every test.

    .venv/bin/python <this file> <scratch dir> <out json>
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIRS = ("memsub", "scripts", "configs", "tests", "modal-runners")
PLAN = "plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe"
CAMP = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
LN32 = f"{CAMP}/p2p5-qwen3-0p6b-screen-v1/learned-n32/volume-evidence/collect-1/learned-n32/cells"
FILES = (f"{PLAN}/probe-priced-ledger.json", f"{CAMP}/pk6/priced-estimate-v6.json",
         f"{CAMP}/pk-campaign-launch/attempt-2/94-billing-hourly-prelim-20261007T1744Z.json",
         f"{LN32}/learned-n32-s0/epoch-1/attempt-1/out/per_example_results.jsonl",
         f"{LN32}/learned-n32-s1/epoch-1/attempt-1/out/per_example_results.jsonl")
TESTS = ["tests/test_sgm_p2p5_readout_probe_validation_contract.py", "tests/test_sgm_p2p5_readout_probe_runner_reaper_reading.py"]
PV, FZ, SL = "scripts/sgm-p2p5-readout-probe-output-validation.py", "scripts/sgm-p2p5-readout-probe-registry-and-schema-freeze.py", "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-logic.py"
RN, RD, LG = "modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py", "scripts/sgm-p2p5-readout-probe-reading.py", "scripts/sgm-p2p5-readout-probe-priced-ledger.py"
A = TESTS[0] + "::"
B = TESTS[1] + "::"
VAL = A + "test_validator_enforces_the_contract_on_every_training_row"
MUTATIONS = {  # name: (file, old, new, aimed test id)
    "num_or_null accepts anything": (PV, "        return got in (NUM, NULL)\n", "        return True\n", A + "test_conforms_unit_cases"),
    "training rows not schema-checked": (PV, "        for r in tele:\n", '        for r in [x for x in tele if "eval" in x]:\n', VAL + "[<lambda>-False0]"),
    "required null dropped": (PV, '            _set(leaves, f"L{last}/{g}", NULL)\n', "            pass\n", A + "test_contract_schema_shape_and_fail_closed"),
    "update_norm made nullable": (PV, 'GRAD_PATHS = (("telemetry_train_row", ("grad_norm",)),',
                                  'GRAD_PATHS = (("telemetry_train_row", ("update_norm",)), ("telemetry_train_row", ("grad_norm",)),',
                                  A + "test_contract_schema_shape_and_fail_closed"),
    "campaign schema extractor used": (PV, "eval_cfg, memsub_sha, registry, None)\n", "eval_cfg, memsub_sha, registry, schema)\n",
                                       A + "test_validator_keeps_the_campaign_checks_and_needs_registry_and_schema"),
    "registry check dropped": (PV, "eval_cfg, memsub_sha, registry, None)\n", "eval_cfg, memsub_sha, None, None)\n",
                               A + "test_validator_keeps_the_campaign_checks_and_needs_registry_and_schema"),
    "missing registry/schema allowed": (PV, "    if registry is None or schema is None:\n", "    if False:\n",
                                        A + "test_validator_keeps_the_campaign_checks_and_needs_registry_and_schema"),
    "COMPLETE uses the campaign validator": (PV, "            problem = validate_probe_outputs(att", "            problem = V.validate_cell_outputs(att",
                                             A + "test_probe_supervisor_complete_transition_uses_the_probe_validator"),
    "head width not changed": (FZ, '        reg[part]["head.weight"] = [64, width]\n', '        reg[part]["head.weight"] = reg[part]["head.weight"]\n',
                               A + "test_frozen_registry_and_schema_equal_their_derivation"),
    "admission ignores the bound app id": (SL, '    if not bound_id(guard.get("app_id", None)):\n', "    if False:\n",
                                           B + "test_admission_refuses_unbound_or_malformed_guards[guard0-no bound app id]"),
    "bool deadline accepted": (SL, "    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0\n",
                               "    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0\n",
                               B + "test_malformed_or_missing_deadline_takes_bounded_abandonment[True]"),
    "infinite deadline accepted": (SL, "    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0\n",
                                   "    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0\n",
                                   B + "test_malformed_or_missing_deadline_takes_bounded_abandonment[inf]"),
    "guard app id mismatch stops anyway": (SL, "    if app_id is not None and app_id != self_app_id:\n", "    if False:\n",
                                           B + "test_missing_or_mismatched_ids_never_stop[store3-ap-self-is not this app]"),
    "missing self id stops anyway": (SL, "    if not bound_id(self_app_id):\n", "    if False:\n",
                                     B + "test_missing_or_mismatched_ids_never_stop[store0-None-own app id unavailable]"),
    "abandonment removed": (SL, '    return ("abandoned or malformed binding" if now > first + ABANDON_S else None), self_app_id, None\n',
                            "    return None, self_app_id, None\n",
                            B + "test_unspawned_and_interrupted_binding_are_abandoned_with_the_self_id"),
    "stopper called without the bound id": (SL, "        stopper(APP_NAME, bound)\n", "        stopper(APP_NAME, None)\n",
                                            B + "test_reap_and_stop_never_passes_none_and_records_stop_errors"),
    "spawn ignores a used guard": (SL, "    if extra:\n", "    if False:\n", B + "test_spawn_guard[guard4-160.0-False]"),
    "collect skips the provenance check": (SL, "    problem = cp.provenance_problem(prov, slot=SLOT)\n", "    problem = None\n",
                                           B + "test_collect_refuses_without_a_bound_id"),
    "collect ignores a failed fetch": (SL, '        if report["evidence"].get("returncode") != 0 or dicts is None:\n', "        if dicts is None:\n",
                                       B + "test_collect_past_deadline_stops_and_failed_fetch_is_unavailable"),
    "GPU app max_containers 2": (RN, "max_containers=1, single_use_containers=True,", "max_containers=2, single_use_containers=True,",
                                 B + "test_decorator_lifetime_arguments"),
    "validator not mounted": (RN, '         .add_local_file(L.VALIDATOR_FILE, f"/root/repo/{L.VALIDATOR_FILE}")\n', "",
                              B + "test_image_inputs_are_the_bound_probe_files"),
    "reading ignores bank dependence": (RD, "GAIN_B if c == P2G.GAIN and b else", "GAIN_B if c == P2G.GAIN else",
                                        B + "test_reading_gain_with_and_without_the_reused_bank_criterion"),
    "reading skips the pairing check": (RD, "        problem = pairing_problem(t_rows[s], r_rows[s])\n", "        problem = None\n",
                                        B + "test_reading_not_shown_and_unavailable_paths"),
    "reading ignores unavailable cells": (RD, "    if bad:\n", "    if False:\n", B + "test_reading_not_shown_and_unavailable_paths"),
    "ledger prices another slot": (LG, 'v6["slots"]["learned-n32"]', 'v6["slots"]["learned-n16"]', B + "test_ledger_prices_the_full_deadline_from_v6"),
    "ledger at billing basis 1.0": (LG, "REAPER_CPU, REAPER_GIB, BASIS = 0.125, 0.25, 2.0", "REAPER_CPU, REAPER_GIB, BASIS = 0.125, 0.25, 1.0",
                                    B + "test_ledger_prices_the_full_deadline_from_v6"),
}
REFREEZE = {PV: "freeze", FZ: "freeze", LG: "ledger"}


def private_copy(dst: Path) -> None:
    for d in DIRS:
        shutil.copytree(ROOT / d, dst / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for rel in FILES:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst / rel)


def refreeze(cp: Path, kind: str) -> str:
    if kind == "freeze":
        for f in ("configs/m4_sgm_p2p5_readout_probe_registry.json", "configs/m4_sgm_p2p5_readout_probe_output_schema.json"):
            (cp / f).unlink()
        cmd = [sys.executable, FZ]
    else:
        (cp / f"{PLAN}/probe-priced-ledger.json").unlink()
        cmd = [sys.executable, LG]
    r = subprocess.run(cmd, cwd=cp, capture_output=True, text=True, timeout=600)
    return f"rc={r.returncode} {r.stdout.strip()[-200:]} {r.stderr.strip()[-200:]}"


def run_tests(cwd: Path) -> tuple[int, list[str], str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", *TESTS], cwd=cwd,
                       capture_output=True, text=True, timeout=1800)
    failed = [ln.split(" ", 1)[1].split(" - ")[0] for ln in r.stdout.splitlines() if ln.startswith(("FAILED ", "ERROR "))]
    return r.returncode, failed, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""


def main():
    scratch, out = Path(sys.argv[1]), Path(sys.argv[2])
    scratch.mkdir(parents=True, exist_ok=False)
    base = scratch / "baseline"
    private_copy(base)
    rc, failed, summary = run_tests(base)
    results = {"baseline": {"rc": rc, "failed": failed, "summary": summary, "ok": rc == 0 and not failed}}
    for i, (name, (rel, old, new, aim)) in enumerate(MUTATIONS.items()):
        cp = scratch / f"m{i:02d}"
        private_copy(cp)
        text = (cp / rel).read_text()
        if text.count(old) != 1:
            results[name] = {"ok": False, "error": f"anchor not found exactly once in {rel}"}
            continue
        (cp / rel).write_text(text.replace(old, new))
        note = refreeze(cp, REFREEZE[rel]) if rel in REFREEZE else None
        rc, failed, summary = run_tests(cp)
        results[name] = {"file": rel, "aimed_test": aim, "refreeze": note, "rc": rc, "failed": failed,
                         "summary": summary, "ok": rc != 0 and aim in failed}
        print(json.dumps({"mutation": name, "ok": results[name]["ok"]}), flush=True)
    results["all_ok"] = all(v["ok"] for v in results.values() if isinstance(v, dict))
    results["shared_tree_untouched"] = "mutations applied only under " + str(scratch)
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"all_ok": results["all_ok"], "n": len(MUTATIONS)}))
    sys.exit(0 if results["all_ok"] else 1)


if __name__ == "__main__":
    main()
