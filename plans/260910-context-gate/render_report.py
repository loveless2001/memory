"""Verify downloaded scientific artifacts and render the local campaign report.

Usage: .venv/bin/python plans/260910-context-gate/render_report.py <run-directory>
The directory must contain launch.json and the downloaded artifacts/ directory.
"""

import hashlib
import json
import sys
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def pct(value):
    return f"{100*value:.2f}%"


def interval(value, percentage=True):
    factor = 100 if percentage else 1
    unit = " pp" if percentage else " tokens"
    lo, hi = value["ci95"]
    return f"{factor*value['estimate']:+.2f}{unit} [{factor*lo:+.2f}, {factor*hi:+.2f}]"


def plot_result(result, root):
    import os
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/memsub-context-gate-matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ["notes_only", "always_retrieve", "self_raw", "confidence", "surface_mlp", "hidden_mlp"]
    labels = ["Notes only", "Always retrieve", "Model R/S", "Confidence", "Surface MLP", "Hidden MLP"]
    colors = ["#7a8a99"] * 5 + ["#d87836"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained")
    for row, split in enumerate(("test", "ood")):
        arms = result["evaluation"][split]["arms"]
        axes[row, 0].barh(labels, [100*arms[n]["accuracy"] for n in names], color=colors)
        axes[row, 1].barh(labels, [arms[n]["mean_input_tokens"] for n in names], color=colors)
        for col in (0, 1):
            axes[row, col].invert_yaxis()
            axes[row, col].spines[["top", "right"]].set_visible(False)
            axes[row, col].grid(axis="x", alpha=.2)
            axes[row, col].set_axisbelow(True)
        axes[row, 0].set_xlim(0, 100)
        axes[row, 0].set_title(f"{split.upper()}: answer accuracy")
        axes[row, 0].set_xlabel("Percent correct")
        axes[row, 1].set_title(f"{split.upper()}: total input cost")
        axes[row, 1].set_xlabel("Mean input tokens, including gating and rebuilt prompts")
    fig.suptitle("ContextGate v1 · frozen 4B · controlled conversation tasks", fontsize=14)
    fig.savefig(root / "accuracy-cost.png", dpi=180)
    fig.savefig(root / "accuracy-cost.pdf")
    plt.close(fig)


def main(directory):
    root = Path(directory)
    artifact = root / "artifacts"
    launch = read(root / "launch.json")
    status = read(artifact / "status.json")
    manifest = read(artifact / "manifest.json")
    assert manifest["source_sha256"] == launch["source_sha256"], "source binding drift"
    assert manifest["run_id"] == launch["run_id"] == status["run_id"]
    count = 0
    if (artifact / "artifact-hashes.json").exists():
        hashes = read(artifact / "artifact-hashes.json")
        for name, expected in hashes.items():
            path = artifact / name
            assert path.is_relative_to(artifact) and ".." not in Path(name).parts
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"hash mismatch: {name}"
        count = len(hashes)
    else:
        assert status["status"] != "complete", "complete run missing hashes"
    app_id = launch["app_id"]
    lines = ["# ContextGate v1 — Modal experiment report", "",
             f"Run: `{launch['run_id']}`. Status: **{status['status']}**.", "",
             f"Modal app: `{app_id}`. Function call: `{launch.get('function_call_id', 'unavailable')}`.",
             f"Measured function elapsed time: {status['elapsed_seconds']:.1f} seconds.",
             "Elapsed function time is distinct from billed usage.", "",
             f"Source SHA-256: `{launch['source_sha256']}`.",
             f"Dataset SHA-256: `{manifest['dataset_sha256']}`.",
             f"Verified {count} downloaded artifact hashes and local/remote source binding.", "",
             "## Scope", "",
             "Frozen Qwen3-4B-Instruct-2507; trained three-seed retrieval-utility controllers.",
             "Controlled synthetic notes/history tasks and forced A/B/C/D or R/S choices.",
             "No claim about natural agent performance, learned summaries, repeated resets, or KV certification.", "",
             "## Data and smoke", "",
             "```json", json.dumps(manifest["split_audit"], indent=2), "```", ""]
    if (root / "billing.json").exists():
        from decimal import Decimal
        billing = read(root / "billing.json")
        assert billing["app_id"] == app_id
        assert all(r["object_id"] == app_id for r in billing["rows"])
        if billing["rows"]:
            cost = sum(Decimal(r["cost"]) for r in billing["rows"])
            lines += [f"Modal-reported app cost: **${cost}** (billing queried {billing['retrieved_at_utc']}).",
                      f"Source command: `{billing['source']}`; retained only this app's rows in `billing.json`.", ""]
    if (artifact / "reader.json").exists():
        reader = read(artifact / "reader.json")
        lines += [f"Reader revision: `{reader['model_revision']}`. GPU: {reader['gpu']}.",
                  f"Backbone parameters: {reader['parameters']:,}; trainable: {reader['trainable_backbone_parameters']}.", ""]
    if (artifact / "smoke-verdict.json").exists():
        smoke = read(artifact / "smoke-verdict.json")
        lines += [f"Smoke passed: **{smoke['pass']}**. Notes {pct(smoke['notes_accuracy'])}, ordinary retrieval "
                  f"{pct(smoke['retrieved_accuracy'])}, oracle evidence {pct(smoke['oracle_accuracy'])}; "
                  f"{smoke['repairs']} repairs.", ""]
    if (artifact / "results.json").exists():
        result = read(artifact / "results.json")
        if result["status"] == "trained":
            plot_result(result, root)
            comparator = result["frozen_policy"]["comparator"]
            test = result["evaluation"]["test"]
            hidden = test["arms"]["hidden_mlp"]
            always = test["arms"]["always_retrieve"]
            extra_tokens = hidden["mean_input_tokens"]/always["mean_input_tokens"]-1
            headline = ["## Result and interpretation", "",
                        f"**{result['verdict']}** under the locked advancement rules. Test accuracy: "
                        f"notes-only {pct(test['arms']['notes_only']['accuracy'])}, ordinary always-retrieve "
                        f"{pct(always['accuracy'])}, surface MLP {pct(test['arms']['surface_mlp']['accuracy'])}, "
                        f"primary hidden MLP {pct(hidden['accuracy'])}.", "",
                        f"The hidden controller uses {100*extra_tokens:.1f}% more input tokens than always-retrieve "
                        "because it evaluates notes before rebuilding the retrieved prompt. Its retrieval decisions "
                        "do not repay that extra pass in this workload. This result is specific to the tested "
                        "reader, controlled notes, retrieval policy, and no-cache-reuse execution.", "",
                        f"Benefit AUC is {test['diagnostics']['hidden_mlp']['benefit_auc']:.4f} for the hidden MLP "
                        f"and {test['diagnostics']['surface_mlp']['benefit_auc']:.4f} for the surface MLP. "
                        "This pilot supplies no evidence of incremental value from internal states over visible "
                        "coverage/confidence features. It does not overturn the earlier, separate KV-policy findings.", ""]
            insertion = lines.index("## Scope")
            lines[insertion:insertion] = headline
            lines += ["## Training", "", "| Controller | Seed | Best epoch | Train loss, initial → selected | Validation loss | Weight change L2 |",
                      "|---|---:|---:|---:|---:|---:|"]
            for name, info in result["training"].items():
                assert info["reload_equivalence"], "checkpoint reload not verified"
                for seed in info["seeds"]:
                    lines.append(f"| {name} | {seed['seed']} | {seed['best_epoch']} | "
                                 f"{seed['initial_train_loss']:.4f} → {seed['selected_train_loss']:.4f} | "
                                 f"{seed['selected_validation_loss']:.4f} | {seed['weight_change_l2']:.4f} |")
            lines += ["", f"Frozen non-hidden comparator: **{comparator}** (selected on calibration).", ""]
            for part in ("test", "ood"):
                evaluation = result["evaluation"][part]
                lines += [f"## {part.upper()}", "", "| Arm | Accuracy | Retrieval | Mean input tokens | Error without retrieval | Oracle-conditioned loss |",
                          "|---|---:|---:|---:|---:|---:|"]
                for name, arm in evaluation["arms"].items():
                    lost = pct(arm["oracle_conditioned_loss"]) if arm["oracle_conditioned_loss"] is not None else "undefined"
                    lines.append(f"| {name} | {pct(arm['accuracy'])} | {pct(arm['retrieval_rate'])} | "
                                 f"{arm['mean_input_tokens']:.1f} | {pct(arm['error_without_retrieval'])} | {lost} |")
                lines += ["", f"Primary hidden MLP minus {comparator}, episode-cluster 95% CIs:", "",
                          f"- Accuracy: {interval(evaluation['paired_accuracy_vs_comparator'])}.",
                          f"- Utility (accuracy − 0.05 × retrieval rate): {interval(evaluation['paired_utility_vs_comparator'])}.",
                          f"- Input tokens: {interval(evaluation['paired_input_tokens_vs_comparator'], False)}.", "",
                          "| Diagnostic | Benefit AUC | Benefit Brier |", "|---|---:|---:|"]
                for name, diag in evaluation["diagnostics"].items():
                    auc = f"{diag['benefit_auc']:.4f}" if diag["benefit_auc"] is not None else "undefined"
                    brier = f"{diag['benefit_brier']:.4f}" if "benefit_brier" in diag else "—"
                    lines.append(f"| {name} | {auc} | {brier} |")
                lines.append("")
            lines += ["## Registered verdict", "", f"**{result['verdict']}**.",
                      f"Accuracy route: {result['advance_routes']['accuracy']}; efficiency route: {result['advance_routes']['efficiency']}.", "",
                      "The verdict uses the pre-registered paired accuracy/utility/token criteria. AUC alone cannot advance it.", "",
                      "![Accuracy and total input cost](accuracy-cost.png)", ""]
        else:
            lines += ["## Training stop", "", f"**{result['status']}**.", "```json", json.dumps(result["class_counts"], indent=2), "```", ""]
    if (artifact / "replay-summary.json").exists():
        replay = read(artifact / "replay-summary.json")
        lines += ["## Sequential replay", "", f"Preselected {replay['rows_per_arm']} test rows per arm; warmup, randomized arm order, actual selected branches.", "",
                  "| Arm | Accuracy | Retrieval | Mean seconds | p95 seconds | Mean input tokens | Decision / answer drift |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for name, arm in replay["arms"].items():
            lines.append(f"| {name} | {pct(arm['accuracy'])} | {pct(arm['retrieval_rate'])} | "
                         f"{arm['mean_wall_seconds']:.4f} | {arm['p95_wall_seconds']:.4f} | {arm['mean_input_tokens']:.1f} | "
                         f"{arm['decision_drift_count']} / {arm['answer_drift_count']} |")
        lines += ["", "Replay latency is descriptive on this GPU and small fixed subset; it did not select thresholds.", ""]
        lines += ["The archive and BM25 selections were already in memory. Timings exclude archive disk/network "
                  "access and index construction and cover constrained single-token outcomes. The table records "
                  "any decision or answer discrepancies between batched capture and sequential replay. These observations were not used "
                  "to refit thresholds or change the verdict.", ""]
    if status["status"] == "failed":
        lines += ["## Failure", "", status.get("error", "See error.txt"), ""]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"report": str(root / "REPORT.md"), "status": status["status"], "verified_artifacts": count}))


if __name__ == "__main__":
    main(sys.argv[1])
