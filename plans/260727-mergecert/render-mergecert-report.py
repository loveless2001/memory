"""Render the private MergeCert report deterministically from evidence JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_REPORT = HERE.parents[1] / "MERGECERT-REPORT.md"


def _percent(value: float) -> str:
    return f"{100 * float(value):.1f}%"


def _p0_table(p0: dict) -> str:
    direction = p0["p0_3"]
    structure = p0["p0_4"]
    low, high = direction["paired_merge_minus_eviction"]["ci95"]
    return "\n".join(
        [
            "| registered check | result | evidence |",
            "|---|---:|---|",
            (
                "| P0.3 merge lost given prior-correct | "
                f"{direction['merge_lost_given_prior_correct']:.4f} | "
                "200-item house pointwise metric |"
            ),
            (
                "| P0.3 eviction lost given prior-correct | "
                f"{direction['eviction_lost_given_prior_correct']:.4f} | "
                "same items and retained budget |"
            ),
            (
                "| paired merge minus eviction | "
                f"{direction['paired_merge_minus_eviction']['mean_diff']:+.4f} "
                f"[{low:+.4f}, {high:+.4f}] | "
                "document-cluster bootstrap 95% CI |"
            ),
            (
                "| merge / eviction mean continuation KL | "
                f"{direction['mean_merge_kl']:.4f} / "
                f"{direction['mean_eviction_kl']:.4f} | fixed continuation |"
            ),
            (
                "| merge exact-slot Jaccard vs StreamingLLM | "
                f"{structure['exact_slot_jaccard']:.4f} | "
                f"{structure['non_singleton_blocks']} non-singleton blocks |"
            ),
            (
                "| merge / StreamingLLM prediction equality | "
                f"{structure['merge_streaming_prediction_equal_rate']:.4f} | "
                "same 200 items |"
            ),
            (
                "| aligned exact / physical max absolute KV difference | "
                f"{structure['aligned_exact_max_abs_kv_difference']:.6g} / "
                f"{structure['physical_max_abs_kv_difference']:.6g} | "
                "exact-slot preservation and non-degeneracy |"
            ),
        ]
    )


def _compute_table(compute: dict, branch: str) -> str:
    phases = ("p0",) if branch == "negative" else ("p0", "q1", "q2", "q3")
    lines = [
        "| phase | compute | measured seconds | actual cost USD | source |",
        "|---|---|---:|---:|---|",
    ]
    for phase in phases:
        row = compute[phase]
        lines.append(
            f"| {phase.upper()} | {row['gpu']} | "
            f"{float(row['gpu_seconds']):.1f} | "
            f"{float(row['cost_usd']):.2f} | {row['source']} |"
        )
    total = sum(float(compute[phase]["cost_usd"]) for phase in phases)
    lines.append(f"| total | - | - | {total:.2f} | measured campaign actual |")
    return "\n".join(lines)


def _delivery_line(delivery: dict) -> str:
    audience = " and ".join(delivery["audience"])
    if delivery["status"] == "confirmed":
        return (
            f"Private delivery: confirmed to {audience} at "
            f"{delivery['delivered_at']} via {delivery['channel']}."
        )
    return f"Private delivery: pending to {audience}; no other use authorized."


def render_report(evidence: dict, delivery: dict) -> str:
    p0 = evidence["p0"]
    negative = bool(p0["stop_q1_q3"])
    branch = "negative" if negative else "positive"
    lines = [
        "# MergeCert — Attention-Weighted KV Merge Placement",
        "",
        "Private to Tyler and Kevin.",
        "",
        _delivery_line(delivery),
        "",
        (
            "This scientific placement run evaluates the method at its best: "
            "the house Qwen3-4B-Instruct-2507 fingerprint, real accumulated "
            "attention, proper paired statistics, and exactly matched retained-"
            "vector budgets. It evaluates the method rather than reproducing "
            "the source repository's evaluation, and every pre-registered "
            "outcome is reportable."
        ),
        "",
        "## P0 — Port and verification",
        "",
        (
            "The port replaces the source approximation with real accumulated "
            "causal attention reduced from query heads to their grouped KV "
            "heads. The sink addition pins logical positions 0-3 identically "
            "for merge, eviction, and StreamingLLM comparators. Recent KV stays "
            "exact; old-region blocks become per-layer, per-KV-head weighted K "
            "and V averages. Retained budgets are exactly 3,072, 2,458, and "
            "410 vectors at 0.25, 0.40, and 0.90."
        ),
        "",
        _p0_table(p0),
        "",
        (
            f"P0.3 direction gate: {'PASS' if p0['p0_3']['pass'] else 'FAIL'}. "
            f"P0.4 non-degeneracy gate: "
            f"{'PASS' if p0['p0_4']['pass'] else 'FAIL'}. "
            f"Real-attention validity: "
            f"{'PASS' if p0['real_attention']['pass'] else 'FAIL'}."
        ),
        "",
    ]
    if negative:
        lines.extend(
            [
                "## Registered stop",
                "",
                (
                    "P0.3 did not reproduce the registered qualitative "
                    "direction. Q1-Q3 were not launched, as required. This is "
                    "a negative placement result for this port and fingerprint; "
                    "no tuning or alternate model was attempted."
                ),
                "",
            ]
        )
    else:
        q1, q2, q3 = evidence["q1"], evidence["q2"], evidence["q3"]
        lines.extend(
            [
                "## Q1 — Two-axis matched-budget placement",
                "",
                q1["markdown_table"].rstrip(),
                "",
                (
                    "The existing 0.25 and 0.40 eviction rows were replayed "
                    "before merge measurement. Frozen and unfrozen rows are "
                    "reference results from their reports of record; the "
                    "zero-compression control is the deterministic noise floor."
                ),
                "",
                "## Q2 — Routability",
                "",
                q2["markdown_table"].rstrip(),
                "",
                q2["registered_reading"],
                "",
                "### F5 fifth-regime row",
                "",
                q2["f5_markdown_table"].rstrip(),
                "",
                "## Q3 — Fragility placement",
                "",
                q3["markdown_table"].rstrip(),
                "",
                q3["interpretation"],
                "",
            ]
        )
    lines.extend(
        [
            "## Compute actuals",
            "",
            _compute_table(evidence["compute"], branch),
            "",
            "## Limitations",
            "",
            (
                "- One house model fingerprint only; this is not a cross-model "
                "comparison."
            ),
            "",
            "- One registered ratio grid; no hyperparameter sweep.",
            "",
            (
                "- The fixed continuation KL is a short smoothness probe, not "
                "a long-horizon generation guarantee."
            ),
            "",
            (
                "- Diagnostic probe refits measure routability; they do not "
                "train or modify the merge policy or base model."
            ),
            "",
            (
                "- This is scientific placement only, not a deployment or "
                "L3-default certification."
            ),
            "",
            "## For the KV-Merge README",
            "",
        ]
    )
    if negative:
        lines.extend(
            [
                (
                    "Supported claim: on the pinned house fingerprint and "
                    "registered 90% point, the real-attention port did not "
                    "establish graceful degradation over matched eviction under "
                    "the pre-registered pointwise gate."
                ),
                "",
                (
                    "Not supported: graceful-degradation, deployment, "
                    "cross-model, or source-evaluation reproduction claims. "
                    "The result localizes the finding to this exact port and "
                    "protocol and does not imply that other implementations "
                    "cannot work."
                ),
            ]
        )
    else:
        direction = p0["p0_3"]
        lines.extend(
            [
                (
                    "Supported claim: at 90% evicted-equivalent budget, "
                    "attention-weighted merging lost "
                    f"{_percent(direction['merge_lost_given_prior_correct'])} "
                    "of prior-correct facts versus "
                    f"{_percent(direction['eviction_lost_given_prior_correct'])} "
                    "for matched contiguous eviction; the paired difference "
                    "and CI are in the P0 table."
                ),
                "",
                (
                    "Supported claim: the merge is structurally and numerically "
                    "distinct from sink plus recent retention while preserving "
                    "its aligned exact slots."
                ),
                "",
                (
                    "Not supported: claims beyond the pinned house model, "
                    "registered budgets, and measured workloads; deployment "
                    "certification and source-repository number reproduction "
                    "were outside scope."
                ),
            ]
        )
    lines.extend(["", "## For the spec", ""])
    if negative:
        lines.append(
            (
                "Draft §13.7 note: attention-weighted merge was evaluated as a "
                "candidate fourth training-free regime point, but the "
                "registered direction gate failed. Record it as a measured "
                "negative placement and do not add a positive regime claim."
            )
        )
    else:
        q1 = evidence["q1"]
        q2 = evidence["q2"]
        q1_better = all(
            q1["summaries"][f"merge-{ratio}"]["lost_prior"]
            < q1["summaries"][f"eviction-{ratio}"]["lost_prior"]
            for ratio in ("0.25", "0.40")
        )
        mechanics = sum(
            q2["ratios"][ratio]["mechanics_refit"]["auc"]
            for ratio in ("0.25", "0.40")
        ) / 2
        if q1_better and mechanics >= 0.70:
            lines.append(
                (
                    "Draft §13.7 note: add merge as the fourth training-free "
                    "regime point. At matched budgets it preserves more "
                    "pointwise facts than contiguous eviction, and its loss is "
                    "mechanics-routable from externally visible block features. "
                    "Keep aggregation, pointwise, routability, and fragility "
                    "axes separate."
                )
            )
        else:
            lines.append(
                (
                    "Draft §13.7 note: record merge as a measured fourth "
                    "candidate rather than a promoted regime point. Its Q1/Q2 "
                    "placement does not jointly support the preservation plus "
                    "visible-mechanics reading; retain the tables and negative "
                    "boundary."
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def load_evidence(plan_dir: Path) -> dict:
    with (plan_dir / "source-provenance.json").open() as handle:
        source = json.load(handle)
    with (plan_dir / "p0-verdict.json").open() as handle:
        p0 = json.load(handle)
    with (plan_dir / "compute-actuals.json").open() as handle:
        compute = json.load(handle)
    evidence = {"source": source, "p0": p0, "compute": compute}
    if not p0["stop_q1_q3"]:
        for key, filename in (
            ("q1", "q1-verdict.json"),
            ("q2", "q2-verdict.json"),
            ("q3", "q3-fragility.json"),
        ):
            with (plan_dir / filename).open() as handle:
                evidence[key] = json.load(handle)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, default=HERE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--delivery", type=Path, default=HERE / "delivery-record.json"
    )
    args = parser.parse_args()
    evidence = load_evidence(args.plan_dir)
    if args.delivery.exists():
        with args.delivery.open() as handle:
            delivery = json.load(handle)
    else:
        delivery = {"status": "pending", "audience": ["Tyler", "Kevin"]}
    args.report.write_text(render_report(evidence, delivery))
    print(args.report)


if __name__ == "__main__":
    main()
