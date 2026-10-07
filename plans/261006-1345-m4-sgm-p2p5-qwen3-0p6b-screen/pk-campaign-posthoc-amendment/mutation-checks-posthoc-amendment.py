"""Post-hoc amendment mutation checks on PRIVATE COPIES (codex 21648: never edit shared source in place). For each
mutation: copy the repo subset into a fresh scratch dir, undo one part of the amendment there, RE-FREEZE the
dependency manifest inside the copy (so the manifest refusal cannot be what catches it), run the focused tests in
the copy, and require the AIMED test among the failures. A baseline copy (no mutation) must pass every test.
The shared tree is only read. Real-evidence tests read the main checkout's fetched evidence via M4_PK_EVIDENCE_REPO.

    .venv/bin/python <this file> <scratch dir> <out json>
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = "plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen"
MANIFEST = "configs/m4_sgm_p2p5_campaign_analysis_manifest.json"
DIRS = ("memsub", "scripts", "configs", "tests", "modal-runners")
TESTS = ["tests/test_sgm_pk_posthoc_validation_amendment.py", "tests/test_sgm_pk_campaign_readings_runner.py"]
FREEZE = ("import importlib.util, json, sys; sys.path.insert(0, '.');"
          "s = importlib.util.spec_from_file_location('m', 'scripts/sgm-p2p5-pk-campaign-analysis-dependency-manifest.py');"
          "m = importlib.util.module_from_spec(s); s.loader.exec_module(m);"
          f"open('{MANIFEST}', 'w').write(json.dumps(m.freeze(), indent=2, sort_keys=True) + chr(10))")
A = "scripts/sgm-p2p5-pk-posthoc-validation-amendment.py"
R = "scripts/sgm-p2p5-pk-campaign-readings.py"
N = "modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py"
T = "tests/test_sgm_pk_posthoc_validation_amendment.py::"
LIM = T + "test_exception_is_limited_to_the_listed_grad_norm_leaves"
BYTES = T + "test_private_copy_byte_changes_are_refused"
MUTATIONS = {  # name: (file, old, new, aimed test id)
    "null-set equality dropped": (A, "    if grad_norm_nulls(tele) != allowed:\n", "    if False:\n",
                                  LIM + "[extra_grad_null]"),
    "update_norm also exempted (codex 21701: unsupported)": (
        A, '            r[NULLABLE_FIELD] = {k: (0.0 if (r["step"], k) in keep else v) for k, v in r[NULLABLE_FIELD].items()}\n',
        '            r[NULLABLE_FIELD] = {k: (0.0 if (r["step"], k) in keep else v) for k, v in r[NULLABLE_FIELD].items()}\n'
        '            r["update_norm"] = {k: (0.0 if v is None else v) for k, v in r["update_norm"].items()}\n',
        LIM + "[update_norm_null]"),
    "frozen numeric grad_norm leaf check dropped": (
        A, '        if not m or m.group(1) not in V.selected_layer_ids(pilot) or frozen.get(f"L{{L}}/{m.group(2)}") != {"num": True}:\n',
        "        if False:\n", LIM + "[unlisted_layer_key]"),
    "FAILED record bytes not bound": (
        A, '    if sha(es.epoch_dir(cell_dir, spec["epoch"]) / "state.json") != spec["state_sha256"]:\n', "    if False:\n",
        BYTES + "[state]"),
    "terminal checkpoint not bound": (
        A, '    if not rec.get("chain") or rec["chain"][-1] != spec["terminal_checkpoint"] or \\\n'
           '            es.verify_chain(cell_dir, [spec["terminal_checkpoint"]]) is not None:\n', "    if False:\n",
        BYTES + "[checkpoint]"),
    "done.json sha not bound": (A, '    if sha(attempt / "done.json") != spec["done_sha256"]:\n', "    if False:\n",
                                BYTES + "[done]"),
    "original failure not required": (
        A, '    if V.validate_cell_outputs(*args, schema) != spec["original_validation"]:\n', "    if False:\n",
        BYTES + "[output]"),
    "checks after the schema stage skipped": (
        A, "    other = V.validate_cell_outputs(*args, None)\n", "    other = None\n",
        T + "test_checks_after_the_schema_stage_still_apply"),
    "FAILED state / original reason not required": (
        A, '    if rec.get("state") != es.FAILED or rec.get("reason") != spec["original_reason"] or rec.get("epoch") != spec["epoch"]:\n',
        '    if rec.get("epoch") != spec["epoch"]:\n', T + "test_private_copy_passes_and_every_binding_is_enforced"),
    "readings: amendment applied to any non-COMPLETE cell": (
        R, '            if rec["state"] != es.COMPLETE and amendment is not None and cid == amendment["cell"]:\n',
        '            if rec["state"] != es.COMPLETE and amendment is not None:\n',
        T + "test_real_evidence_original_gate_unavailable_and_amended_gate_binds_exactly_18"),
    "readings: original gate not recorded": (
        R, '        _orig, original = bind_cells(root, admitted, report["identity"]["memsub"], grid, registry, schema)\n',
        "        original = None\n", T + "test_readings_label_the_campaign_and_both_n_and_keep_the_original_reading"),
    "readings: per-N label dropped": (
        R, '        v["label"] = AMD.LABEL\n', "        pass\n",
        T + "test_readings_label_the_campaign_and_both_n_and_keep_the_original_reading"),
    "runner: any FAILED cell accepted": (
        N, '               and not (amendment and c == amendment["cell"] and v.get("state") == "FAILED"\n',
        '               and not (amendment and v.get("state") == "FAILED"\n',
        T + "test_runner_accepts_only_the_spec_cell_with_the_original_reason"),
    "runner: original reason not required": (
        N, '                        and v.get("reason") == amendment["original_reason"])}\n', "                        )}\n",
        T + "test_runner_accepts_only_the_spec_cell_with_the_original_reason"),
    "runner: record not bound to the spec sha": (
        N, '    if rec.get("result") != "amended_valid" or rec.get("spec_sha256") != file_sha(root / AMENDMENT_SPEC) \\\n',
        '    if rec.get("result") != "amended_valid" \\\n',
        T + "test_runner_amendment_gate_requires_the_sha_bound_amended_valid_record"),
}


def private_copy(dst: Path) -> None:
    manifest = json.loads((ROOT / MANIFEST).read_text())
    for d in DIRS:
        shutil.copytree(ROOT / d, dst / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for rel in [*manifest["analysis"], *manifest["launch"]]:
        if not (dst / rel).exists():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dst / rel)


def run_tests(cwd: Path) -> tuple[int, list[str], str]:
    env = {**os.environ, "M4_PK_EVIDENCE_REPO": str(ROOT)}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider", *TESTS], cwd=cwd,
                       capture_output=True, text=True, env=env, timeout=900)
    failed = [ln.split(" ", 2)[1] for ln in r.stdout.splitlines() if ln.startswith("FAILED ")]
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
        subprocess.run([sys.executable, "-c", FREEZE], cwd=cp, check=True)
        rc, failed, summary = run_tests(cp)
        results[name] = {"file": rel, "aimed_test": aim, "rc": rc, "failed": failed, "summary": summary,
                         "ok": rc != 0 and aim in failed}
    results["all_ok"] = all(v["ok"] for v in results.values() if isinstance(v, dict))
    results["shared_tree_untouched"] = "mutations applied only under " + str(scratch)
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"all_ok": results["all_ok"], "n": len(MUTATIONS)}))
    sys.exit(0 if results["all_ok"] else 1)


if __name__ == "__main__":
    main()
