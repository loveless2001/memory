"""Validate the private MergeCert report and write its evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_REPORT = HERE.parents[1] / "MERGECERT-REPORT.md"
DEFAULT_MANIFEST = HERE / "artifact-manifest.json"
EXPECTED_SOURCE = {
    "repository": "https://github.com/jkdkr2439/KV-Merge",
    "commit": "cd4ed948d62231449dbab9669608bbb4fd220713",
    "files": {
        "README.md": (
            "edfd5236d99dab5d6e4bf80b74dd79a54ffd94cec4b7066511dc6fd7ae7cae17"
        ),
        "benchmarks/modal_kv_real_bench.py": (
            "518b2d2cd4b652f4cc83ef9c82593fe624301986e0e3e22780ee9f0bfe423bb8"
        ),
        "lego_server.py": (
            "f1df91c8af05cf4ea5000f4027450bf91e5e269f4e922da8979fc0885d6ff228"
        ),
    },
}


def _renderer_module():
    path = HERE / "render-mergecert-report.py"
    spec = importlib.util.spec_from_file_location("mergecert_report_renderer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_evidence(evidence: dict) -> str:
    source = evidence.get("source", {})
    if (
        source.get("repository") != EXPECTED_SOURCE["repository"]
        or source.get("commit") != EXPECTED_SOURCE["commit"]
        or source.get("files") != EXPECTED_SOURCE["files"]
        or source.get("port", {}).get("model_id")
        != "Qwen/Qwen3-4B-Instruct-2507"
    ):
        raise ValueError("source provenance differs from the registered port")

    p0 = evidence.get("p0", {})
    required_p0 = {"sample", "p0_3", "p0_4", "real_attention"}
    if not required_p0 <= set(p0):
        raise ValueError("P0 evidence is incomplete")
    component_pass = all(
        p0[key].get("pass") is True
        for key in ("sample", "p0_3", "p0_4", "real_attention")
    )
    if p0.get("p0_pass") is not component_pass:
        raise ValueError("P0 component verdicts are inconsistent with p0_pass")
    if p0.get("stop_q1_q3") is not (not component_pass):
        raise ValueError("P0 stop/pass fields are inconsistent")
    if p0["sample"].get("n_items") != 200:
        raise ValueError("P0 evidence does not contain the registered 200 items")
    branch = "negative" if p0["stop_q1_q3"] else "positive"
    if branch == "positive":
        for phase in ("q1", "q2", "q3"):
            if evidence.get(phase, {}).get("pass") is not True:
                raise ValueError(f"{phase.upper()} evidence is missing or failed")
    elif any(phase in evidence for phase in ("q1", "q2", "q3")):
        raise ValueError("negative P0 branch must not contain Q1-Q3 evidence")
    phases = ("p0",) if branch == "negative" else ("p0", "q1", "q2", "q3")
    compute = evidence.get("compute", {})
    for phase in phases:
        row = compute.get(phase, {})
        if (
            not row.get("gpu")
            or float(row.get("gpu_seconds", -1)) < 0
            or float(row.get("cost_usd", -1)) < 0
            or not row.get("source")
        ):
            raise ValueError(f"{phase.upper()} compute actuals are incomplete")
    return branch


def validate_report_text(
    report: str,
    evidence: dict,
    delivery: dict,
    *,
    require_delivery: bool,
) -> dict:
    if re.search(r"https?://", report):
        raise ValueError("report contains a public URL")
    for forbidden in ("Qwen2.5", "deployment-certified", "TODO", "TBD"):
        if forbidden in report:
            raise ValueError(f"report contains forbidden marker {forbidden}")
    if re.search(r"\|\s*\?\s*\|", report):
        raise ValueError("report contains a question-mark result cell")
    if delivery.get("audience") != ["Tyler", "Kevin"]:
        raise ValueError("private delivery audience must be Tyler and Kevin")
    if require_delivery:
        confirmed = (
            delivery.get("status") == "confirmed"
            and bool(delivery.get("delivered_at"))
            and bool(delivery.get("channel"))
        )
        waived = (
            delivery.get("status") == "waived"
            and bool(delivery.get("waived_at"))
            and bool(delivery.get("basis"))
        )
        if not (confirmed or waived):
            raise ValueError("private delivery is neither confirmed nor waived")
    branch = _validate_evidence(evidence)
    renderer = _renderer_module()
    expected = renderer.render_report(evidence, delivery)
    if report != expected:
        raise ValueError("report differs from deterministic evidence rendering")
    required_headings = {
        "## P0 — Port and verification",
        "## Compute actuals",
        "## Limitations",
        "## For the KV-Merge README",
        "## For the spec",
    }
    if not required_headings <= set(report.splitlines()):
        raise ValueError("report is missing a required section")
    if branch == "positive":
        for heading in (
            "## Q1 — Two-axis matched-budget placement",
            "## Q2 — Routability",
            "## Q3 — Fragility placement",
            "### F5 fifth-regime row",
        ):
            if heading not in report:
                raise ValueError(f"positive report is missing {heading}")
    return {
        "pass": True,
        "branch": branch,
        "delivery_status": delivery["status"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, default=HERE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--delivery", type=Path, default=HERE / "delivery-record.json"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--require-delivery", action="store_true")
    args = parser.parse_args()
    renderer = _renderer_module()
    evidence = renderer.load_evidence(args.plan_dir)
    if args.delivery.exists():
        with args.delivery.open() as handle:
            delivery = json.load(handle)
    else:
        delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}
    report = args.report.read_text()
    result = validate_report_text(
        report,
        evidence,
        delivery,
        require_delivery=args.require_delivery,
    )
    input_paths = [
        args.report,
        args.plan_dir / "source-provenance.json",
        args.plan_dir / "p0-verdict.json",
        args.plan_dir / "compute-actuals.json",
    ]
    if result["branch"] == "positive":
        input_paths.extend(
            [
                args.plan_dir / "q1-verdict.json",
                args.plan_dir / "q2-verdict.json",
                args.plan_dir / "q3-fragility.json",
            ]
        )
    if args.delivery.exists():
        input_paths.append(args.delivery)
    manifest = {
        "validation": result,
        "files": {
            str(path): {
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in input_paths
        },
    }
    with args.manifest.open("w") as handle:
        json.dump(manifest, handle, indent=1, allow_nan=False)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
