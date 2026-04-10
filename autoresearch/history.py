from __future__ import annotations

from pathlib import Path

from autoresearch.artifacts import load_public_artifacts
from autoresearch.domain import RunReport
from autoresearch.runtime_paths import history_path


_CURRENT_HISTORY_COLUMNS = (
    "run_id",
    "benchmark",
    "dataset",
    "candidate",
    "model",
    "validation_score",
    "rank",
    "backend",
    "mode",
    "advisors",
    "selection_origin",
    "advice",
    "artifact",
    "run_best_candidate",
    "run_best_validation",
    "agent_best_candidate",
    "agent_best_validation",
    "dataset_model_best_agent",
    "dataset_model_best_candidate",
    "dataset_model_best_validation",
)

def _history_header() -> str:
    header = " | ".join(_CURRENT_HISTORY_COLUMNS)
    divider = " | ".join("---" for _ in _CURRENT_HISTORY_COLUMNS)
    return (
        "# History\n\n"
        f"| {header} |\n"
        f"| {divider} |\n"
    )


def ensure_history_header(root: Path, agent_dir: Path) -> Path:
    target_path = history_path(root, agent_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        target_path.write_text(_history_header(), encoding="utf-8")
    return target_path


def append_history(agent_dir: Path, report: RunReport, root: Path) -> None:
    history_output_path = ensure_history_header(root, agent_dir)

    artifacts = load_public_artifacts(root)
    mine = [artifact for artifact in artifacts if artifact["agent_name"] == report.agent_name]
    personal_best = max(
        mine,
        key=lambda item: float(item["best_result"]["validation_score"]),
    )
    run_best_candidate = report.best_result.candidate_name
    run_best_validation = report.best_result.validation_score

    lines = history_output_path.read_text(encoding="utf-8").rstrip() + "\n"
    for result in report.results:
        artifact_rel = report.artifact_path.relative_to(root).as_posix()
        same_model = [
            (artifact, candidate)
            for artifact in artifacts
            for candidate in artifact["results"]
            if artifact["dataset_id"] == report.dataset_id and candidate["model_family"] == result.model_family
        ]
        best_artifact, global_model_best = max(
            same_model,
            key=lambda item: float(item[1]["validation_score"]),
        )
        lines += (
            f"| {report.run_id} | {report.benchmark_id} | {report.dataset_id} | "
            f"{result.candidate_name} | {result.model_family} | "
            f"{result.validation_score:.6f} | {result.rank} | {report.backend_name} | "
            f"{report.policy_mode} | {','.join(report.advisors) or '-'} | {report.selection_origin} | "
            f"{','.join(report.advice_snapshot_paths) or '-'} | "
            f"`{artifact_rel}` | {run_best_candidate} | {run_best_validation:.6f} | "
            f"{personal_best['best_result']['candidate_name']} | "
            f"{float(personal_best['best_result']['validation_score']):.6f} | "
            f"{best_artifact['agent_name']} | {global_model_best['candidate_name']} | "
            f"{float(global_model_best['validation_score']):.6f} |\n"
        )
    history_output_path.write_text(lines, encoding="utf-8")
