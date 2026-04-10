from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoresearch.agent_report import append_report_entry
from autoresearch.catalog import load_catalog
from autoresearch.runner import ExperimentRunner
from autoresearch.runtime_paths import sequence_path


@dataclass(frozen=True)
class RoundSpec:
    name: str
    analysis: str
    model: dict[str, Any]


@dataclass(frozen=True)
class PreprocRoundSpec:
    name: str
    analysis: str
    preprocessing: dict[str, Any]


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, (int, float)):
        return str(value)
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def build_submission_text(benchmark: str, backend: str, round_spec: RoundSpec) -> str:
    lines = [
        f'benchmark = "{benchmark}"',
        f'backend = "{backend}"',
        "",
        "[[candidates]]",
        f'name = "{round_spec.name}"',
        'model_family = "mlp"',
        "",
        "[candidates.model]",
    ]
    for key, value in round_spec.model.items():
        lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def build_preproc_submission_text(
    benchmark: str,
    backend: str,
    fixed_model: dict[str, Any],
    round_spec: PreprocRoundSpec,
) -> str:
    lines = [
        f'benchmark = "{benchmark}"',
        f'backend = "{backend}"',
        "",
        "[[candidates]]",
        f'name = "{round_spec.name}"',
        'model_family = "mlp"',
        "",
        "[candidates.preprocessing]",
    ]
    for key, value in round_spec.preprocessing.items():
        lines.append(f"{key} = {_toml_value(value)}")
    if fixed_model:
        lines.extend(
            [
                "",
                "[candidates.model]",
            ]
        )
        for key, value in fixed_model.items():
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def write_submission(agent_dir: Path, benchmark: str, backend: str, round_spec: RoundSpec) -> None:
    text = build_submission_text(benchmark=benchmark, backend=backend, round_spec=round_spec)
    (agent_dir / "submission.toml").write_text(text, encoding="utf-8")


def write_preproc_submission(
    agent_dir: Path,
    benchmark: str,
    backend: str,
    fixed_model: dict[str, Any],
    round_spec: PreprocRoundSpec,
) -> None:
    text = build_preproc_submission_text(
        benchmark=benchmark,
        backend=backend,
        fixed_model=fixed_model,
        round_spec=round_spec,
    )
    (agent_dir / "submission.toml").write_text(text, encoding="utf-8")


def run_round_sequence(
    root: Path,
    agent_dir: Path,
    benchmark: str,
    backend: str,
    rounds: list[RoundSpec],
    submission_writer=write_submission,
) -> tuple[list[tuple[int, RoundSpec, float]], Any]:
    root = Path(root)
    agent_dir = Path(agent_dir)
    catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
    runner = ExperimentRunner(root=root, catalog=catalog)

    summary_rows: list[tuple[int, RoundSpec, float]] = []
    for index, round_spec in enumerate(rounds, start=1):
        submission_writer(agent_dir, benchmark, backend, round_spec)
        report = runner.run_agent_submission(agent_dir)
        append_report_entry(root, agent_dir, report.run_id, round_spec.analysis)
        summary_rows.append((index, round_spec, report.best_result.validation_score))

    final_report = runner.finalize_agent(agent_dir)
    best_round_spec = next(
        (round_spec for round_spec in rounds if round_spec.name == final_report.best_result.candidate_name),
        None,
    )
    if best_round_spec is not None:
        submission_writer(agent_dir, benchmark, backend, best_round_spec)
    return summary_rows, final_report


def write_sequence_summary(
    agent_dir: Path,
    dataset_name: str,
    benchmark: str,
    backend: str,
    rounds: list[tuple[int, RoundSpec, float]],
    final_report: Any,
) -> None:
    lines = [
        "# Sequence",
        "",
        f"Agent: `{agent_dir.name}`",
        "",
        f"- Dataset: `{dataset_name}`",
        f"- Benchmark: `{benchmark}`",
        "- Model family constraint: `mlp` only",
        "- Preprocessing / resampling: left at framework defaults on every round",
        "- Shared split seed: `42`",
        f"- Backend used: `{backend}`",
        f"- Search protocol: `{len(rounds)}` validation-only rounds, then one hidden-test reveal",
        "",
        "## Validation Rounds",
        "",
        "| round | candidate | model options | validation_score |",
        "| --- | --- | --- | --- |",
    ]
    for index, round_spec, score in rounds:
        option_text = ", ".join(f"{key}={value}" for key, value in round_spec.model.items())
        lines.append(
            f"| {index} | `{round_spec.name}` | `{option_text}` | `{score:.6f}` |"
        )

    lines.extend(
        [
            "",
            "## Final Selection",
            "",
            "- Finalize rule used: choose the best validation candidate; if validation ties, higher hidden-test score wins during finalize.",
            f"- Finalized candidate: `{final_report.best_result.candidate_name}`",
            f"- Final validation score: `{final_report.best_result.validation_score:.6f}`",
            f"- Hidden test score after finalize: `{final_report.best_result.test_score:.6f}`",
            "",
        ]
    )
    output_path = sequence_path(agent_dir.parent.parent, agent_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_preproc_sequence_summary(
    agent_dir: Path,
    dataset_name: str,
    benchmark: str,
    backend: str,
    rounds: list[tuple[int, PreprocRoundSpec, float]],
    final_report: Any,
    fixed_model: dict[str, Any],
) -> None:
    lines = [
        "# Sequence",
        "",
        f"Agent: `{agent_dir.name}`",
        "",
        f"- Dataset: `{dataset_name}`",
        f"- Benchmark: `{benchmark}`",
        "- Model family constraint: `mlp` only",
        (
            f"- Fixed model: `{', '.join(f'{key}={value}' for key, value in fixed_model.items())}`"
            if fixed_model
            else "- Fixed model: `sklearn` MLP defaults (no model options submitted)"
        ),
        "- Only preprocessing changed across rounds",
        "- Resampling stayed at framework defaults",
        "- Shared split seed: `42`",
        f"- Backend used: `{backend}`",
        f"- Search protocol: `{len(rounds)}` validation-only rounds, then one hidden-test reveal",
        "",
        "## Validation Rounds",
        "",
        "| round | candidate | preprocessing | validation_score |",
        "| --- | --- | --- | --- |",
    ]
    for index, round_spec, score in rounds:
        option_text = ", ".join(f"{key}={value}" for key, value in round_spec.preprocessing.items())
        lines.append(
            f"| {index} | `{round_spec.name}` | `{option_text}` | `{score:.6f}` |"
        )

    lines.extend(
        [
            "",
            "## Final Selection",
            "",
            "- Finalize rule used: choose the best validation candidate; if validation ties, higher hidden-test score wins during finalize.",
            f"- Finalized candidate: `{final_report.best_result.candidate_name}`",
            f"- Final validation score: `{final_report.best_result.validation_score:.6f}`",
            f"- Hidden test score after finalize: `{final_report.best_result.test_score:.6f}`",
            "",
        ]
    )
    output_path = sequence_path(agent_dir.parent.parent, agent_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
