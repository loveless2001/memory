"""Fail-closed validation for the private MergeCert Q1 report bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import math
import re
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_REPORT = ROOT / "MERGECERT-Q1-REPORT.md"
DEFAULT_MANIFEST = HERE / "artifact-manifest.json"
REQUIRED_HEADINGS = {
    "## Settled 0.90 result",
    "## Q1 — Moderate-ratio placement",
    "## Per-domain slices",
    "## Registered readings",
    "## Conditional Q2/Q3",
    "## Compute provenance",
    "## For the KV-Merge README",
    "## For the spec",
    "## Limitations",
}
EXPECTED_ARMS = {
    "control-0.00",
    "eviction-0.25",
    "eviction-0.40",
    "merge-0.25",
    "merge-0.40",
}
EXPECTED_DOMAINS = {"financial", "legal", "code", "literature"}
EXPECTED_UPSTREAM = {
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
EXPECTED_ADDENDUM = {
    "path": "MERGECERT-Q1.md",
    "sha256": "faf1239bf21ed3ec4e33421645694cc7a70ecc04765961af04c3f4ff2f106df7",
}
EXPECTED_SETTLED_P0 = {
    "verdict_path": "plans/260727-mergecert/p0-verdict.json",
    "verdict_sha256": (
        "4dff3d8806a12fd751d352bbbac94b1bef3b9a5b8db20bbea9da221df06ccb2a"
    ),
    "raw_path": "plans/260727-mergecert/p0-direction-200.json",
    "raw_sha256": (
        "2d12ae1de090f3d93ba3cad97f68a49f543cd4a0398078c625e2641981f10f6c"
    ),
}
EXPECTED_PARENT_SOURCE_SHA256 = (
    "cbaaec6a20cb4e53ab36a56f377c91c6bd97b8028f1fd60e2c63bdb759576930"
)
MARKDOWN_ESCAPE_PATTERN = re.compile(
    r"\\([\\`*_[\]{}()#+\-.!|>?~])"
)
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
MARKDOWN_WRAPPER_PATTERN = re.compile(r"[*_~`]+")
HTML_TAG_PATTERN = re.compile(r"<[^>\n]+>")
PUBLIC_URL_PATTERN = re.compile(
    r"(?:(?:https?:)?//)[A-Za-z0-9]",
    re.IGNORECASE,
)
QUESTION_CELL_PATTERN = re.compile(r"\|\s*\?\s*\|")
QWEN25_PATTERN = re.compile(r"\bqwen2\.5\b", re.IGNORECASE)
CLAIM_SEGMENT_PATTERN = re.compile(
    r"(?:[.;,\n]+|\b(?:and|but)\b)",
    re.IGNORECASE,
)
NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|never|unconfirmed|unrecorded|neither)\b",
    re.IGNORECASE,
)
DEPLOYMENT_PATTERN = re.compile(
    r"\b(?:deploy|deployed|deploying|deploys|deployment(?!-relevant\b))\b",
    re.IGNORECASE,
)
TRANSMISSION_PATTERN = re.compile(
    r"\b(?:transmission|delivery)\b",
    re.IGNORECASE,
)
REPORT_PATTERN = re.compile(r"\breport\b", re.IGNORECASE)
RECIPIENT_PATTERN = re.compile(r"\b(?:tyler|kevin)\b", re.IGNORECASE)
AFFIRMATIVE_PATTERN = re.compile(
    r"\b(?:succeed(?:ed|s|ing)?|success(?:ful(?:ly)?)?|"
    r"complet(?:e|ed|ion)|ready|certif(?:ied|ication)|"
    r"approv(?:ed|al)|production|live|operational|"
    r"sent|deliver(?:ed|y)|transmitt(?:ed|al)|shared|"
    r"receiv(?:e|ed|es|ing))\b",
    re.IGNORECASE,
)
EXPECTED_PHASE_LABELS = {
    "q1": "Q1",
    "q2_q3": "Q2/Q3",
}
MODAL_APP_ID = r"ap-[A-Za-z0-9]{22}"
APP_ID_PATTERN = re.compile(MODAL_APP_ID)
BILLING_SOURCE_PATTERN = re.compile(
    rf"Modal billing report (?P<date>\d{{4}}-\d{{2}}-\d{{2}}) "
    rf"for (?P<noun>app|apps) "
    rf"(?P<ids>{MODAL_APP_ID}(?:(?:, | and ){MODAL_APP_ID})*)"
)


def _renderer_module():
    path = HERE / "render-report.py"
    spec = importlib.util.spec_from_file_location(
        "mergecert_q1_report_renderer", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inspection_text(unescaped_report: str) -> str:
    normalized = MARKDOWN_ESCAPE_PATTERN.sub(r"\1", unescaped_report)
    normalized = MARKDOWN_LINK_PATTERN.sub(r"\1", normalized)
    normalized = HTML_TAG_PATTERN.sub("", normalized)
    return MARKDOWN_WRAPPER_PATTERN.sub("", normalized)


def _positive_claim(report: str) -> str | None:
    for segment in CLAIM_SEGMENT_PATTERN.split(report):
        if not segment.strip() or NEGATION_PATTERN.search(segment):
            continue
        if DEPLOYMENT_PATTERN.search(segment):
            return segment.strip()
        if TRANSMISSION_PATTERN.search(segment):
            return segment.strip()
        if (
            RECIPIENT_PATTERN.search(segment)
            and REPORT_PATTERN.search(segment)
        ):
            return segment.strip()
        if (
            RECIPIENT_PATTERN.search(segment)
            and AFFIRMATIVE_PATTERN.search(segment)
        ):
            return segment.strip()
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_file_hashes(evidence: dict) -> None:
    files = evidence.get("_files")
    if not isinstance(files, dict) or not files:
        raise ValueError("artifact hash metadata is missing")
    relative_paths = []
    for name, metadata in files.items():
        path = metadata.get("path")
        if not isinstance(path, Path) or not path.is_file():
            raise ValueError(f"artifact {name} is missing")
        actual_hash = _sha256(path)
        actual_bytes = path.stat().st_size
        if (
            metadata.get("sha256") != actual_hash
            or metadata.get("bytes") != actual_bytes
        ):
            raise ValueError(f"artifact hash or byte count drift for {name}")
        relative_path = metadata.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"artifact path metadata is missing for {name}")
        relative_paths.append(relative_path)
    if len(relative_paths) != len(set(relative_paths)):
        raise ValueError("artifact paths are not unique")


def _validate_loaded_evidence(evidence: dict) -> None:
    for name in ("source", "p0", "q1", "trigger", "conditional", "compute"):
        path = evidence["_files"][name]["path"]
        with path.open() as handle:
            loaded = json.load(handle)
        if json.dumps(loaded, sort_keys=True) != json.dumps(
            evidence[name], sort_keys=True
        ):
            raise ValueError(f"loaded evidence differs from hashed file {name}")
    for name in ("q2", "q3"):
        if name not in evidence:
            continue
        with evidence["_files"][name]["path"].open() as handle:
            loaded = json.load(handle)
        if json.dumps(loaded, sort_keys=True) != json.dumps(
            evidence[name], sort_keys=True
        ):
            raise ValueError(f"loaded evidence differs from hashed file {name}")


def _validate_source(evidence: dict) -> None:
    source = evidence.get("source", {})
    files = evidence["_files"]
    if (
        source.get("protocol") != "MERGECERT-Q1"
        or source.get("model_id") != "Qwen/Qwen3-4B-Instruct-2507"
        or source.get("ratios") != [0.25, 0.4]
        or source.get("sink_token_count") != 4
        or source.get("upstream_commit") != EXPECTED_UPSTREAM["commit"]
    ):
        raise ValueError("source provenance differs from registration")
    upstream_files = source.get("upstream_files")
    if upstream_files != EXPECTED_UPSTREAM["files"]:
        raise ValueError("source provenance file hashes are incomplete")
    addendum = source.get("addendum", {})
    settled = source.get("settled_p0", {})
    if (
        addendum != EXPECTED_ADDENDUM
        or settled != EXPECTED_SETTLED_P0
        or source.get("parent_source_provenance_sha256")
        != EXPECTED_PARENT_SOURCE_SHA256
    ):
        raise ValueError("source provenance differs from registration")
    if (
        addendum.get("sha256") != files["addendum"]["sha256"]
        or settled.get("verdict_sha256") != files["p0"]["sha256"]
        or settled.get("raw_sha256") != files["p0_raw"]["sha256"]
        or source.get("parent_source_provenance_sha256")
        != files["parent_source"]["sha256"]
    ):
        raise ValueError("source provenance artifact hash mismatch")
    expected_paths = {
        "addendum": addendum.get("path"),
        "p0": settled.get("verdict_path"),
        "p0_raw": settled.get("raw_path"),
    }
    if any(
        files[name]["relative_path"] != expected
        for name, expected in expected_paths.items()
    ):
        raise ValueError("source provenance artifact path mismatch")
    p0 = evidence.get("p0", {})
    if (
        p0.get("p0_3", {}).get("pass") is not False
        or p0.get("p0_4", {}).get("pass") is not True
        or p0.get("real_attention", {}).get("pass") is not True
        or p0.get("p0_pass") is not False
        or p0.get("stop_q1_q3") is not True
    ):
        raise ValueError("settled P0 verdict is not the registered negative")


def _expected_favorable(intervals: dict) -> tuple[list[str], list[str]]:
    pointwise = []
    aggregation = []
    for ratio in ("0.25", "0.40"):
        row = intervals[ratio]
        if row["lost_prior"]["ci95"][1] < 0:
            pointwise.append(f"{ratio}:lost_prior")
        if row["mean_kl"]["ci95"][1] < 0:
            aggregation.append(f"{ratio}:mean_kl")
        if row["acc_delta"]["ci95"][0] > 0:
            aggregation.append(f"{ratio}:acc_delta")
    return pointwise, aggregation


def _validate_interval(interval: dict, label: str) -> None:
    values = [interval.get("mean_diff"), *(interval.get("ci95") or [])]
    if (
        not isinstance(interval.get("ci95"), list)
        or len(interval["ci95"]) != 2
        or not all(_is_number(value) for value in values)
        or interval["ci95"][0] > interval["ci95"][1]
    ):
        raise ValueError(f"Q1 interval is malformed for {label}")


def _validate_q1(evidence: dict) -> None:
    q1 = evidence.get("q1", {})
    if (
        q1.get("pass") is not True
        or q1.get("documents") != 20
        or q1.get("archived_m1_replay_pass") is not True
        or set(q1.get("summaries", {})) != EXPECTED_ARMS
        or set(q1.get("references", {}))
        != {"frozen_subsample", "unfrozen_compactor"}
        or set(q1.get("per_domain", {})) != EXPECTED_DOMAINS
    ):
        raise ValueError("Q1 verdict is incomplete")
    for domain, rows in q1["per_domain"].items():
        if set(rows) != EXPECTED_ARMS:
            raise ValueError(f"Q1 per-domain arms are incomplete for {domain}")
    numeric_fields = ("mean_kl", "accuracy_delta", "lost_prior")
    for group_name in ("summaries", "references"):
        for row_name, row in q1[group_name].items():
            if any(not _is_number(row.get(field)) for field in numeric_fields):
                raise ValueError(
                    f"Q1 numeric evidence is malformed for {row_name}"
                )
    for domain, rows in q1["per_domain"].items():
        for arm, row in rows.items():
            if (
                any(not _is_number(row.get(field)) for field in numeric_fields)
                or any(
                    not isinstance(row.get(field), int) or row[field] < 0
                    for field in (
                        "documents",
                        "aggregation_probes",
                        "needle_probes",
                    )
                )
            ):
                raise ValueError(
                    f"Q1 numeric evidence is malformed for {domain}/{arm}"
                )
    intervals = q1.get("paired_merge_minus_eviction", {})
    if set(intervals) != {"0.25", "0.40"}:
        raise ValueError("Q1 paired intervals are incomplete")
    for ratio, row in intervals.items():
        if set(row) != {"lost_prior", "mean_kl", "acc_delta"}:
            raise ValueError(f"Q1 paired metrics are incomplete for {ratio}")
        for metric, interval in row.items():
            _validate_interval(interval, f"{ratio}:{metric}")

    pointwise, aggregation = _expected_favorable(intervals)
    favorable = pointwise + aggregation
    readings = q1.get("registered_readings", {})
    expected = {
        "r1": "R1" if pointwise else "R2",
        "r3": (
            "aggregation-positive" if aggregation else "aggregation-negative"
        ),
        "pointwise_favorable": pointwise,
        "aggregation_favorable": aggregation,
        "favorable_intervals": favorable,
        "run_q2_q3": bool(favorable),
    }
    if readings != expected:
        raise ValueError("Q1 registered readings are inconsistent")
    if (
        q1.get("run_q2_q3") is not bool(favorable)
        or q1.get("favorable_intervals") != favorable
    ):
        raise ValueError("Q1 trigger fields are inconsistent")


def _validate_trigger(evidence: dict) -> None:
    trigger = evidence.get("trigger", {})
    q1 = evidence["q1"]
    source = evidence["source"]
    expected = {
        "protocol": "MERGECERT-Q1",
        "run_q2_q3": q1["run_q2_q3"],
        "favorable_intervals": q1["favorable_intervals"],
        "q1_verdict_sha256": evidence["_files"]["q1"]["sha256"],
        "addendum_sha256": source["addendum"]["sha256"],
        "p0_verdict_sha256": source["settled_p0"]["verdict_sha256"],
    }
    if trigger != expected:
        raise ValueError("Q1 trigger differs from the registered verdict")


def _validate_conditional(evidence: dict) -> str:
    conditional = evidence.get("conditional", {})
    trigger = evidence["trigger"]
    if (
        conditional.get("protocol") != "MERGECERT-Q1"
        or conditional.get("q1_trigger_sha256")
        != evidence["_files"]["trigger"]["sha256"]
    ):
        raise ValueError("conditional work is not bound to the Q1 trigger")
    if trigger["run_q2_q3"]:
        if conditional.get("status") != "completed":
            raise ValueError("conditional work was not completed after trigger")
        for name in ("q2", "q3"):
            if name not in evidence:
                raise ValueError(f"conditional {name.upper()} evidence drift")
            declaration = conditional.get(name, {})
            embedded_trigger = evidence[name].get("q1_trigger")
            embedded_hash = evidence[name].get("q1_trigger_sha256")
            if name == "q2":
                f5_table = evidence[name].get("f5_markdown_table")
                if not isinstance(f5_table, str) or not f5_table.strip():
                    raise ValueError("conditional Q2 F5 evidence is missing")
            if (
                declaration.get("path")
                != evidence["_files"][name]["relative_path"]
                or declaration.get("sha256")
                != evidence["_files"][name]["sha256"]
                or evidence[name].get("pass") is not True
                or (
                    embedded_trigger is not None
                    and embedded_trigger != trigger
                )
                or (
                    embedded_hash is not None
                    and embedded_hash
                    != evidence["_files"]["trigger"]["sha256"]
                )
            ):
                raise ValueError(f"conditional {name.upper()} evidence drift")
        return "completed"
    renderer = _renderer_module()
    if (
        conditional.get("status") != "skipped"
        or conditional.get("reason") != renderer.SKIP_REASON
        or any(name in evidence for name in ("q2", "q3"))
    ):
        raise ValueError("conditional skip differs from the registered rule")
    return "skipped"


def _validate_compute(evidence: dict) -> float:
    compute = evidence.get("compute", {})
    ceiling = compute.get("ceiling_usd")
    total = compute.get("total_cost_usd")
    if not _is_number(ceiling) or float(ceiling) != 45.0:
        raise ValueError("compute ceiling is not the registered $45")
    if not _is_number(total) or float(total) > float(ceiling):
        raise ValueError("compute total exceeds the registered ceiling")
    phases = compute.get("phases")
    expected_phases = (
        {"q1", "q2_q3"}
        if evidence["trigger"]["run_q2_q3"]
        else {"q1"}
    )
    if not isinstance(phases, dict) or set(phases) != expected_phases:
        raise ValueError("compute billing records are missing")
    calculated = 0.0
    seen_app_ids = set()
    for phase_key, row in phases.items():
        phase = row.get("phase")
        if phase != EXPECTED_PHASE_LABELS[phase_key]:
            raise ValueError(f"compute phase binding is invalid for {phase_key}")
        cost = row.get("cost_usd")
        if (
            not _is_number(row.get("gpu_seconds"))
            or float(row["gpu_seconds"]) < 0
            or not _is_number(cost)
            or float(cost) < 0
        ):
            raise ValueError(f"billing numeric actuals are incomplete for {phase}")
        runs = row.get("runs")
        if (
            not isinstance(runs, list)
            or not runs
            or any(
                not isinstance(run, dict)
                or not isinstance(run.get("app_id"), str)
                or APP_ID_PATTERN.fullmatch(run["app_id"]) is None
                for run in runs
            )
        ):
            raise ValueError(f"billing app ID is incomplete for {phase}")
        app_ids = [run["app_id"] for run in runs]
        if (
            len(app_ids) != len(set(app_ids))
            or seen_app_ids.intersection(app_ids)
        ):
            raise ValueError(f"billing app ID is duplicated for {phase}")
        seen_app_ids.update(app_ids)
        source = row.get("source")
        source_match = (
            BILLING_SOURCE_PATTERN.fullmatch(source)
            if isinstance(source, str)
            else None
        )
        if source_match is None:
            raise ValueError(f"billing source is incomplete for {phase}")
        try:
            date.fromisoformat(source_match.group("date"))
        except ValueError as error:
            raise ValueError(f"billing date is invalid for {phase}") from error
        source_app_ids = APP_ID_PATTERN.findall(source_match.group("ids"))
        expected_noun = "app" if len(app_ids) == 1 else "apps"
        if (
            source_match.group("noun") != expected_noun
            or source_app_ids != app_ids
        ):
            raise ValueError(f"billing source is incomplete for {phase}")
        calculated += float(cost)
    if not math.isclose(calculated, float(total), rel_tol=0, abs_tol=1e-9):
        raise ValueError("compute total differs from billing records")
    return float(total)


def _validate_privacy(evidence: dict) -> str:
    privacy = evidence.get("privacy", {})
    if privacy != {
        "status": "local-private",
        "audience": ["Tyler", "Kevin"],
        "transmission_recorded": False,
    }:
        raise ValueError("privacy disposition is not local and untransmitted")
    return privacy["status"]


def validate_report_text(report: str, evidence: dict) -> dict:
    """Validate evidence and require byte-for-byte canonical report text."""

    _validate_file_hashes(evidence)
    _validate_source(evidence)
    _validate_q1(evidence)
    _validate_trigger(evidence)
    conditional_status = _validate_conditional(evidence)
    total = _validate_compute(evidence)
    privacy_status = _validate_privacy(evidence)
    _validate_loaded_evidence(evidence)

    unescaped_report = html.unescape(report)
    inspection_text = _inspection_text(unescaped_report)
    if (
        PUBLIC_URL_PATTERN.search(unescaped_report)
        or PUBLIC_URL_PATTERN.search(inspection_text)
    ):
        raise ValueError("report contains a public URL")
    if QUESTION_CELL_PATTERN.search(inspection_text):
        raise ValueError("report contains a question-mark result cell")
    if match := QWEN25_PATTERN.search(inspection_text):
        raise ValueError(f"report contains forbidden claim {match.group(0)}")
    if claim := _positive_claim(inspection_text):
        raise ValueError(f"report contains forbidden claim {claim}")
    if REQUIRED_HEADINGS - set(report.splitlines()):
        raise ValueError("report is missing a required heading")
    if "Private to Tyler and Kevin." not in report:
        raise ValueError("report is missing the private audience line")

    renderer = _renderer_module()
    if report != renderer.render_report(evidence):
        raise ValueError("report differs from deterministic evidence rendering")
    return {
        "pass": True,
        "conditional_status": conditional_status,
        "privacy_status": privacy_status,
        "total_cost_usd": total,
    }


def write_artifact_manifest(
    report_path: Path,
    evidence: dict,
    validation: dict,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict:
    """Write hashes and byte counts for the report and every loaded input."""

    report_path = Path(report_path)
    root = Path(evidence["_root"])
    entries = {
        report_path.resolve().relative_to(root.resolve()).as_posix(): {
            "sha256": _sha256(report_path),
            "bytes": report_path.stat().st_size,
        }
    }
    for metadata in evidence["_files"].values():
        entries[metadata["relative_path"]] = {
            "sha256": _sha256(metadata["path"]),
            "bytes": metadata["path"].stat().st_size,
        }
    manifest = {
        "validation": validation,
        "files": dict(sorted(entries.items())),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=1, allow_nan=False) + "\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, default=HERE)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    renderer = _renderer_module()
    evidence = renderer.load_evidence(args.plan_dir, root=args.root)
    report = args.report.read_text()
    result = validate_report_text(report, evidence)
    manifest = write_artifact_manifest(
        args.report, evidence, result, args.manifest
    )
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
