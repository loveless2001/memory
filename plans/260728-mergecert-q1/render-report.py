"""Render the private MergeCert Q1 report from hash-bound JSON evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from memsub.mergecert_q1_registration import (
    Q1_REGISTRATION_PENDING,
    Q1_REGISTRATION_SHA256,
    validate_q1_registration_schema,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_REPORT = ROOT / "MERGECERT-Q1-REPORT.md"
SKIP_REASON = (
    "Q2 and Q3 were skipped because no merge-minus-eviction 95% interval was "
    "favorable under the registered Q1 rule."
)
R1_TEXT = (
    "R1 pointwise: merge CI-below eviction on lost|prior at either ratio "
    "→ the preservation instinct holds at moderate ratios; scoped spectrum "
    'row earned ("blend-preserving at moderate ratios, collapsing at '
    'extreme"), §13.7 note upgraded accordingly.'
)
R2_TEXT = (
    "R2 pointwise: CI-overlapping or worse (the E2 interference prediction "
    "— averaging manufactures confusable-sibling blending) → placement "
    "closes negative on the needle axis at all ratios; the theory's "
    '"merging is structurally worst-case for bindings" reading is confirmed '
    "at deployment-relevant compression."
)
R3_TEXT = (
    "R3 aggregation: independent of R1/R2, report where merge KL/accΔ lands "
    "relative to eviction — a merge that loses needles but wins aggregation "
    "is STILL a coherent scoped result (gist tier behind a gate), and the "
    "two-axis protocol exists precisely to say so without blending."
)
ARMS = (
    "control-0.00",
    "eviction-0.25",
    "eviction-0.40",
    "merge-0.25",
    "merge-0.40",
)
ARM_LABELS = {
    "control-0.00": "zero-compression control",
    "eviction-0.25": "eviction 0.25",
    "eviction-0.40": "eviction 0.40",
    "merge-0.25": "MERGE 0.25",
    "merge-0.40": "MERGE 0.40",
}
BUDGET_MODE = "archived-m1-per-document-matched-physical-v1"
FROZEN_REFERENCE_RELATIVE = "FULLRECIPE-REPORT.md"
CLEAN_UNFROZEN_REFERENCE_RELATIVE = (
    "plans/260719-2328-e1full-unfrozen-full-recipe/"
    "summary-e1full-clean-v1-n60.json"
)
FROZEN_REFERENCE_SHA256 = (
    "58b95e104c0c1ab2e2bb47a222a3672bb5dbc58dee815de4ea02c3abcef5969d"
)
CLEAN_UNFROZEN_REFERENCE_SHA256 = (
    "a7636b54148e7133237af68bf63fbc23811d5ce80417f8447711a89a559dc2a8"
)
FROZEN_N60_PATTERN = re.compile(
    r"All arms were re-certified at n = 60 with paired CIs; the frozen"
    r".*?full-recipe row becomes KL (?P<mean_kl>\d+\.\d+)"
    r" / accΔ (?P<accuracy_delta>[+-]\d+\.\d+)"
    r" / pointwise (?P<lost_prior>\d+\.\d+)",
    re.DOTALL,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _record(files: dict, name: str, path: Path, root: Path) -> None:
    files[name] = {
        "path": path,
        "relative_path": _relative(path, root),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _load_reference_context(
    frozen_path: Path,
    clean_unfrozen_path: Path,
) -> list[dict]:
    if _sha256(frozen_path) != FROZEN_REFERENCE_SHA256:
        raise ValueError("frozen reference source hash differs")
    if _sha256(clean_unfrozen_path) != CLEAN_UNFROZEN_REFERENCE_SHA256:
        raise ValueError("clean unfrozen reference source hash differs")

    frozen_match = FROZEN_N60_PATTERN.search(frozen_path.read_text())
    if frozen_match is None:
        raise ValueError("frozen n=60 reference statement is missing")

    clean = _read_json(clean_unfrozen_path)
    provenance = clean.get("provenance", {})
    overlap = provenance.get("overlap_audit", {})
    reports = clean.get("reports", {}).get("eviction-matched", [])
    if (
        overlap.get("certification_documents") != 60
        or overlap.get("document_overlap") != []
        or overlap.get("item_overlap") != []
        or len(reports) != 60
        or any(row.get("eviction_fraction") != 0.499 for row in reports)
    ):
        raise ValueError(
            "clean unfrozen n=60 reference provenance is invalid"
        )
    clean_row = clean.get("summary", {}).get("compactor-d1")
    if not isinstance(clean_row, dict):
        raise ValueError("clean unfrozen d1 reference summary is missing")

    return [
        {
            "label": "frozen full-recipe d1 (n=60)",
            "budget_note": "different n=60 population; ~50% compression",
            "n": 60,
            "mean_kl": float(frozen_match.group("mean_kl")),
            "accuracy_delta": float(
                frozen_match.group("accuracy_delta")
            ),
            "lost_prior": float(frozen_match.group("lost_prior")),
        },
        {
            "label": "clean unfrozen d1 (n=60)",
            "budget_note": (
                "clean held-out n=60 population; 49.9% compression"
            ),
            "n": 60,
            "mean_kl": clean_row["mean_kl"],
            "accuracy_delta": clean_row["acc_delta"],
            "lost_prior": clean_row["lost_prior"],
        },
    ]


def load_evidence(plan_dir: Path = HERE, *, root: Path = ROOT) -> dict:
    """Load the complete report input set and retain byte-level provenance."""

    if Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING:
        raise ValueError(
            "Q1 report is pending finalized registration extraction and review"
        )
    plan_dir = Path(plan_dir)
    root = Path(root)
    files = {}
    fixed = {
        "source": plan_dir / "source-provenance.json",
        "registration": plan_dir / "q1-registration.json",
        "q1": plan_dir / "q1-verdict.json",
        "trigger": plan_dir / "q1-trigger.json",
        "conditional": plan_dir / "conditional-work.json",
        "compute": plan_dir / "compute-actuals.json",
    }
    evidence = {}
    for name, path in fixed.items():
        if (
            name == "registration"
            and _sha256(path) != Q1_REGISTRATION_SHA256
        ):
            raise ValueError(
                "Q1 finalized registration differs from its literal binding"
            )
        evidence[name] = _read_json(path)
        _record(files, name, path, root)

    source = evidence["source"]
    referenced = {
        "addendum": root / source["addendum"]["path"],
        "registration_source": (
            root / source["q1_registration_source"]["path"]
        ),
        "parent_source": (
            root / "plans/260727-mergecert/source-provenance.json"
        ),
        "p0": root / source["settled_p0"]["verdict_path"],
        "p0_raw": root / source["settled_p0"]["raw_path"],
        "frozen_reference": root / FROZEN_REFERENCE_RELATIVE,
        "clean_unfrozen_reference": (
            root / CLEAN_UNFROZEN_REFERENCE_RELATIVE
        ),
    }
    for name, path in referenced.items():
        _record(files, name, path, root)
    validate_q1_registration_schema(
        evidence["registration"],
        source_registration=_read_json(referenced["registration_source"]),
    )
    evidence["p0"] = _read_json(referenced["p0"])
    evidence["reference_context"] = _load_reference_context(
        referenced["frozen_reference"],
        referenced["clean_unfrozen_reference"],
    )

    conditional = evidence["conditional"]
    if conditional.get("status") == "completed":
        amendment = conditional.get("q2_amendment", {})
        if not isinstance(amendment, dict) or not isinstance(
            amendment.get("path"), str
        ):
            raise ValueError("completed conditional work lacks a Q2 amendment")
        amendment_path = root / amendment["path"]
        evidence["q2_amendment"] = _read_json(amendment_path)
        _record(files, "q2_amendment", amendment_path, root)
        for name in ("q2", "q3"):
            path = root / conditional[name]["path"]
            evidence[name] = _read_json(path)
            _record(files, name, path, root)

    evidence["privacy"] = {
        "status": "local-private",
        "audience": ["Tyler", "Kevin"],
        "transmission_recorded": False,
    }
    evidence["_files"] = files
    evidence["_root"] = root
    return evidence


def _format_ci(interval: dict) -> str:
    low, high = interval["ci95"]
    return f"{interval['mean_diff']:+.4f} [{low:+.4f}, {high:+.4f}]"


def _settled_table(p0: dict) -> str:
    direction = p0["p0_3"]
    paired = direction["paired_merge_minus_eviction"]
    return "\n".join(
        [
            "| settled 0.90 check | value |",
            "|---|---:|",
            (
                "| merge lost given prior-correct | "
                f"{direction['merge_lost_given_prior_correct']:.6f} |"
            ),
            (
                "| eviction lost given prior-correct | "
                f"{direction['eviction_lost_given_prior_correct']:.6f} |"
            ),
            (
                "| merge - eviction, 95% CI | "
                f"{_format_ci(paired)} |"
            ),
            (
                "| registered P0.3 direction gate | "
                f"{'PASS' if direction['pass'] else 'FAIL'} |"
            ),
        ]
    )


def _placement_table(q1: dict) -> str:
    lines = [
        "| matched Q1 arm | agg KL | agg accΔ | "
        "pointwise lost|prior |",
        "|---|---:|---:|---:|",
    ]
    for arm in (
        "eviction-0.25",
        "merge-0.25",
        "eviction-0.40",
        "merge-0.40",
        "control-0.00",
    ):
        row = q1["summaries"][arm]
        lines.append(
            f"| {ARM_LABELS[arm]} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} |"
        )
    return "\n".join(lines)


def _reference_context_table(rows: list[dict]) -> str:
    lines = [
        "| reference regime | population / budget note | n | agg KL | "
        "agg accΔ | pointwise lost|prior |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['budget_note']} | {row['n']} | "
            f"{row['mean_kl']:.4f} | {row['accuracy_delta']:+.4f} | "
            f"{row['lost_prior']:.3f} |"
        )
    return "\n".join(lines)


def _interval_table(q1: dict) -> str:
    lines = [
        "| ratio | merge - eviction metric | paired estimate and 95% CI |",
        "|---:|---|---:|",
    ]
    for ratio in ("0.25", "0.40"):
        row = q1["paired_merge_minus_eviction"][ratio]
        for metric, label in (
            ("lost_prior", "lost|prior"),
            ("mean_kl", "agg KL"),
            ("acc_delta", "agg accΔ"),
        ):
            lines.append(
                f"| {ratio} | {label} | {_format_ci(row[metric])} |"
            )
    return "\n".join(lines)


def _domain_table(q1: dict) -> str:
    lines = [
        "| domain | arm | documents | agg probes | needle probes | "
        "agg KL | agg accΔ | lost|prior |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for domain in ("financial", "legal", "code", "literature"):
        for arm in ARMS:
            row = q1["per_domain"][domain][arm]
            lines.append(
                f"| {domain} | {ARM_LABELS[arm]} | {row['documents']} | "
                f"{row['aggregation_probes']} | {row['needle_probes']} | "
                f"{row['mean_kl']:.4f} | {row['accuracy_delta']:+.3f} | "
                f"{row['lost_prior']:.3f} |"
            )
    return "\n".join(lines)


def _registered_readings(q1: dict) -> str:
    reading = q1["registered_readings"]
    selected = (
        f"Measured verdicts: {reading['r1']} and {reading['r3']}."
    )
    return "\n\n".join((R1_TEXT, R2_TEXT, R3_TEXT, selected))


def _conditional_section(evidence: dict) -> str:
    conditional = evidence["conditional"]
    if conditional["status"] == "skipped":
        return conditional["reason"]
    return "\n\n".join(
        [
            (
                "The registered Q1 trigger authorized amended variable-context "
                "Q2/Q3. It preserves the original 30,847-item population and "
                "uses per-item matched physical budgets rather than the failed "
                "fixed-context protocol."
            ),
            "### Amended variable-context Q2 — Routability",
            evidence["q2"]["markdown_table"].rstrip(),
            evidence["q2"]["registered_reading"],
            "### F5 fifth-regime row",
            evidence["q2"]["f5_markdown_table"].rstrip(),
            "### Amended variable-context Q3 — Fragility",
            evidence["q3"]["markdown_table"].rstrip(),
            evidence["q3"]["interpretation"],
        ]
    )


def _compute_table(compute: dict) -> str:
    lines = [
        "| phase | compute | measured seconds | actual cost USD | "
        "billing source | app IDs |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in compute["phases"].values():
        app_ids = [run["app_id"] for run in row["runs"]]
        lines.append(
            f"| {row['phase']} | {row['gpu']} | "
            f"{float(row['gpu_seconds']):.1f} | "
            f"{float(row['cost_usd']):.2f} | "
            f"{row['source']} | {', '.join(app_ids)} |"
        )
    lines.append(
        f"| total | - | - | {float(compute['total_cost_usd']):.2f} | "
        f"registered ceiling ${float(compute['ceiling_usd']):.0f} | - |"
    )
    return "\n".join(lines)


def _favorable_lines(q1: dict) -> list[str]:
    labels = {
        "lost_prior": "lost-prior",
        "mean_kl": "mean-KL",
        "acc_delta": "accuracy-delta",
    }
    return [
        (
            "Measured favorable axis: "
            f"{interval.split(':', 1)[0]} "
            f"{labels[interval.split(':', 1)[1]]}."
        )
        for interval in q1["favorable_intervals"]
    ]


def _readme_moderate_story(q1: dict) -> str:
    reading = q1["registered_readings"]
    pointwise_ratios = [
        interval.split(":", 1)[0]
        for interval in reading["pointwise_favorable"]
    ]
    remaining_ratios = [
        ratio for ratio in ("0.25", "0.40") if ratio not in pointwise_ratios
    ]
    if pointwise_ratios:
        pointwise = (
            "At moderate compression, merge earns a scoped pointwise row at "
            f"{' and '.join(pointwise_ratios)}"
        )
        if remaining_ratios:
            pointwise += (
                f"; the {' and '.join(remaining_ratios)} pointwise "
                f"{'interval does' if len(remaining_ratios) == 1 else 'intervals do'} "
                "not separate."
            )
        else:
            pointwise += " across both registered ratios."
    else:
        pointwise = (
            "At moderate compression, merge does not earn the pointwise axis "
            "at either registered ratio."
        )

    aggregation_labels = {
        "mean_kl": "mean-KL",
        "acc_delta": "accuracy-delta",
    }
    aggregation = [
        (
            f"{interval.split(':', 1)[0]} "
            f"{aggregation_labels[interval.split(':', 1)[1]]}"
        )
        for interval in reading["aggregation_favorable"]
    ]
    if aggregation:
        aggregation_story = (
            "It earns a scoped aggregation row at "
            f"{' and '.join(aggregation)}."
        )
    else:
        aggregation_story = "It also does not earn the aggregation axis."
    return f"{pointwise} {aggregation_story}"


def render_report(evidence: dict) -> str:
    """Return the canonical report; all measurements come from evidence."""

    q1 = evidence["q1"]
    reading = q1["registered_readings"]
    lines = [
        "# MergeCert Q1 — Moderate-Ratio Placement",
        "",
        "Private to Tyler and Kevin.",
        "",
        (
            "Local/private report only. Transmission is not recorded. "
            "No public artifact is authorized."
        ),
        "",
        "## Settled 0.90 result",
        "",
        (
            "The parent P0 result remains settled and was not rerun by this "
            "addendum."
        ),
        "",
        _settled_table(evidence["p0"]),
        "",
        "## Q1 — Moderate-ratio placement",
        "",
        _placement_table(q1),
        "",
        (
            "Per-document matched physical budgets preserve the exact "
            "archived M1 population. 4,096-token source/model inputs retain "
            "3,072 tokens at 0.25 and 2,458 tokens at 0.40. Shorter archived "
            "contexts use their measured matched budgets."
        ),
        "",
        "### Historical context — not directly budget/population matched",
        "",
        (
            "These latest n=60 reference rows use different populations and "
            "approximately 50% compression. They are historical context, "
            "not Q1-matched comparators."
        ),
        "",
        _reference_context_table(evidence["reference_context"]),
        "",
        _interval_table(q1),
        "",
        "## Per-domain slices",
        "",
        _domain_table(q1),
        "",
        "## Registered readings",
        "",
        _registered_readings(q1),
        "",
        "## Conditional Q2/Q3",
        "",
        _conditional_section(evidence),
        "",
        "## Compute provenance",
        "",
        _compute_table(evidence["compute"]),
        "",
        "## For the KV-Merge README",
        "",
        (
            "The registered 0.90 result remains negative for this exact port "
            "and house fingerprint."
        ),
        "",
        _readme_moderate_story(q1),
        "",
    ]
    if reading["r1"] == "R2":
        lines.extend(
            [
                (
                    "At 0.25 and 0.40, the pointwise registered reading is R2; "
                    "the measured confidence intervals are in the Q1 table."
                ),
                "",
                (
                    "A merge-plus-anchor design is a theoretically motivated "
                    "future direction for preserving bindings while retaining "
                    "merge behavior, but it was not tested in this campaign."
                ),
            ]
        )
    lines.extend(_favorable_lines(q1))
    lines.extend(
        [
            "",
            "## For the spec",
            "",
            (
                f"Draft §13.7 note: record {reading['r1']} and "
                f"{reading['r3']} for the pinned Qwen3 fingerprint and the "
                "measured 0.25/0.40 protocol. Keep aggregation and pointwise "
                "axes separate."
            ),
            "",
            "## Limitations",
            "",
            "- One pinned house model fingerprint.",
            "",
            "- Two registered moderate ratios; no sweep or tuning.",
            "",
            "- The 0.90 result is imported from the settled parent evidence.",
            "",
            (
                "- Scientific placement only; this is not a deployment "
                "certification."
            ),
            "",
            "- No hybrid or anchor variant was run.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, default=HERE)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    evidence = load_evidence(args.plan_dir, root=args.root)
    args.report.write_text(render_report(evidence))
    print(args.report)


if __name__ == "__main__":
    main()
