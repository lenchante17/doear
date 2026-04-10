from __future__ import annotations

from pathlib import Path
from typing import Any

from autoresearch.artifacts import (
    load_finalized_artifacts,
    load_public_artifacts,
    select_best_final_rows,
    select_best_validation_rows,
)
from autoresearch.domain import RunReport
from autoresearch.runtime_paths import final_report_path, leaderboard_path


def write_final_report(root: Path, agent_dir: Path, final_report: RunReport) -> None:
    if final_report.benchmark_id == "multiple":
        summary_line = "Finalized run set across multiple benchmarks."
    else:
        summary_line = f"Finalized run set for benchmark `{final_report.benchmark_id}`."

    lines = [
        f"# Final Report for `{final_report.agent_name}`",
        "",
        summary_line,
        "",
        "## Best Candidate",
        "",
        f"- Candidate: `{final_report.best_result.candidate_name}`",
        f"- Benchmark: `{final_report.best_result.benchmark_id or final_report.benchmark_id}`",
        f"- Dataset: `{final_report.best_result.dataset_id or final_report.dataset_id}`",
        f"- Model: `{final_report.best_result.model_family}`",
        f"- Validation Score: `{final_report.best_result.validation_score:.6f}`",
        f"- Test Score: `{final_report.best_result.test_score:.6f}`",
        "",
        "## Final Table",
        "",
        "| benchmark | dataset | model | candidate | validation_score | test_score |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in final_report.results:
        lines.append(
            f"| {result.benchmark_id or final_report.benchmark_id} | "
            f"{result.dataset_id or final_report.dataset_id} | "
            f"{result.model_family} | {result.candidate_name} | "
            f"{result.validation_score:.6f} | {result.test_score:.6f} |"
        )
    output_path = final_report_path(root, agent_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_validation_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| dataset | model | agent | candidate | benchmark | validation_score | backend | config |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(
        rows,
        key=lambda item: (
            -float(item["validation_score"]),
            item["dataset"],
            item["model"],
            item["agent"],
        ),
    ):
        lines.append(
            f"| {row['dataset']} | {row['model']} | {row['agent']} | {row['candidate']} | "
            f"{row['benchmark']} | {row['validation_score']:.6f} | "
            f"{row['backend']} | {row['config_summary']} |"
        )
    return lines


def _render_test_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| dataset | model | agent | candidate | benchmark | validation_score | test_score | backend | config |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(
        rows,
        key=lambda item: (
            -float(item["test_score"]),
            item["dataset"],
            item["model"],
            item["agent"],
        ),
    ):
        lines.append(
            f"| {row['dataset']} | {row['model']} | {row['agent']} | {row['candidate']} | "
            f"{row['benchmark']} | {row['validation_score']:.6f} | {row['test_score']:.6f} | "
            f"{row['backend']} | {row['config_summary']} |"
        )
    return lines


def write_leaderboard(root: Path) -> None:
    validation_rows = select_best_validation_rows(load_public_artifacts(root))
    final_rows = select_best_final_rows(load_finalized_artifacts(root))
    lines = [
        "# Leaderboard",
        "",
        "Validation results stay visible during search. Test results appear only after an agent is finalized.",
        "",
        "## Validation Set Results",
        "",
    ]
    if validation_rows:
        lines.extend(_render_validation_table(validation_rows))
    else:
        lines.append("No validation runs yet.")
    lines.extend(
        [
            "",
            "## Test Set Results",
            "",
        ]
    )
    if final_rows:
        lines.extend(_render_test_table(final_rows))
    else:
        lines.append("No finalized agents yet.")
    output_path = leaderboard_path(root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
