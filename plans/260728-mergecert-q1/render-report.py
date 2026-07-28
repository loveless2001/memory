"""Render the private MergeCert Q1 report from hash-bound JSON evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


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


def load_evidence(plan_dir: Path = HERE, *, root: Path = ROOT) -> dict:
    """Load the complete report input set and retain byte-level provenance."""

    plan_dir = Path(plan_dir)
    root = Path(root)
    files = {}
    fixed = {
        "source": plan_dir / "source-provenance.json",
        "q1": plan_dir / "q1-verdict.json",
        "trigger": plan_dir / "q1-trigger.json",
        "conditional": plan_dir / "conditional-work.json",
        "compute": plan_dir / "compute-actuals.json",
    }
    evidence = {}
    for name, path in fixed.items():
        evidence[name] = _read_json(path)
        _record(files, name, path, root)

    source = evidence["source"]
    referenced = {
        "addendum": root / source["addendum"]["path"],
        "parent_source": (
            root / "plans/260727-mergecert/source-provenance.json"
        ),
        "p0": root / source["settled_p0"]["verdict_path"],
        "p0_raw": root / source["settled_p0"]["raw_path"],
    }
    for name, path in referenced.items():
        _record(files, name, path, root)
    evidence["p0"] = _read_json(referenced["p0"])

    conditional = evidence["conditional"]
    if conditional.get("status") == "completed":
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
        "| arm (matched retained budget) | agg KL | agg accΔ | "
        "pointwise lost|prior |",
        "|---|---:|---:|---:|",
    ]
    for arm in ("eviction-0.25", "eviction-0.40"):
        row = q1["summaries"][arm]
        lines.append(
            f"| {ARM_LABELS[arm]} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} |"
        )
    for key, label in (
        ("frozen_subsample", "frozen subsample (reference)"),
        ("unfrozen_compactor", "unfrozen compactor (reference)"),
    ):
        row = q1["references"][key]
        lines.append(
            f"| {label} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} |"
        )
    for arm in ("merge-0.25", "merge-0.40", "control-0.00"):
        row = q1["summaries"][arm]
        lines.append(
            f"| {ARM_LABELS[arm]} | {row['mean_kl']:.4f} | "
            f"{row['accuracy_delta']:+.3f} | {row['lost_prior']:.3f} |"
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
            "The registered Q1 trigger authorized the conditional work.",
            "### Q2 — Routability",
            evidence["q2"]["markdown_table"].rstrip(),
            evidence["q2"]["registered_reading"],
            "### F5 fifth-regime row",
            evidence["q2"]["f5_markdown_table"].rstrip(),
            "### Q3 — Fragility",
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
            "archived M1 population. 4096-token documents retain 3072 tokens "
            "at 0.25 and 2458 tokens at 0.40. Shorter archived contexts use "
            "their measured matched budgets."
        ),
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
