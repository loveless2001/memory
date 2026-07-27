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
    p0 = evidence.get("p0", {})
    required_p0 = {"sample", "p0_3", "p0_4", "real_attention"}
    if not required_p0 <= set(p0):
        raise ValueError("P0 evidence is incomplete")
    if p0.get("stop_q1_q3") == p0.get("p0_pass"):
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
    if require_delivery and (
        delivery.get("status") != "confirmed"
        or not delivery.get("delivered_at")
        or not delivery.get("channel")
    ):
        raise ValueError("private delivery is not confirmed")
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
