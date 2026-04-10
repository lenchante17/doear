from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import shutil
import sys
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from autoresearch.agent_profiles import render_program
from autoresearch.policy import render_default_policy
from autoresearch.scaffold import DEFAULT_SUBMISSION


OUTPUT_BASE = Path("/tmp/toy_research_isolated_experiments")
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SOURCE_CATALOG_PATH = REPO_ROOT / "experiments" / "benchmark_catalog.toml"
SOURCE_SEARCH_SPACE_PATH = REPO_ROOT / "experiments" / "search_spaces" / "mlp_advisory_v1.toml"


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    mode: str
    advisors: tuple[str, ...]
    agent_profile: str | None

    @property
    def condition_name(self) -> str:
        return self.name


EXPERIMENT_SPECS = (
    ExperimentSpec("tpe_direct", "direct", ("optuna_tpe",), None),
    ExperimentSpec("smac_direct", "direct", ("smac3",), None),
    ExperimentSpec("ratchet_plain", "agent", (), "01_ratchet"),
    ExperimentSpec("screening_plain", "agent", (), "02_screening_doe"),
    ExperimentSpec("advanced_plain", "agent", (), "03_advanced_doe"),
    ExperimentSpec("ratchet_tpe", "agent", ("optuna_tpe",), "01_ratchet"),
    ExperimentSpec("screening_tpe", "agent", ("optuna_tpe",), "02_screening_doe"),
    ExperimentSpec("advanced_tpe", "agent", ("optuna_tpe",), "03_advanced_doe"),
    ExperimentSpec("ratchet_smac", "agent", ("smac3",), "01_ratchet"),
    ExperimentSpec("screening_smac", "agent", ("smac3",), "02_screening_doe"),
    ExperimentSpec("advanced_smac", "agent", ("smac3",), "03_advanced_doe"),
    ExperimentSpec("ratchet_tpe_smac", "agent", ("optuna_tpe", "smac3"), "01_ratchet"),
    ExperimentSpec("screening_tpe_smac", "agent", ("optuna_tpe", "smac3"), "02_screening_doe"),
    ExperimentSpec("advanced_tpe_smac", "agent", ("optuna_tpe", "smac3"), "03_advanced_doe"),
)


def _copy_autoresearch_tree(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def _write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents.strip() + "\n", encoding="utf-8")


def _ensure_symlink(link_path: Path, target_path: Path) -> None:
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_dir() and not link_path.is_symlink():
            shutil.rmtree(link_path)
        else:
            link_path.unlink()
    os.symlink(target_path, link_path, target_is_directory=target_path.is_dir())


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def _load_catalog_payload() -> dict[str, object]:
    return tomllib.loads(SOURCE_CATALOG_PATH.read_text(encoding="utf-8"))


def _render_subset_catalog(benchmark_id: str) -> str:
    payload = _load_catalog_payload()
    datasets = payload.get("datasets")
    benchmarks = payload.get("benchmarks")
    if not isinstance(datasets, dict) or not isinstance(benchmarks, dict):
        raise ValueError("benchmark catalog is missing datasets or benchmarks tables")
    benchmark_row = benchmarks.get(benchmark_id)
    if not isinstance(benchmark_row, dict):
        raise ValueError(f"Unknown benchmark {benchmark_id!r}")
    dataset_id = benchmark_row.get("dataset")
    if not isinstance(dataset_id, str):
        raise ValueError(f"Benchmark {benchmark_id!r} is missing dataset")
    dataset_row = datasets.get(dataset_id)
    if not isinstance(dataset_row, dict):
        raise ValueError(f"Dataset {dataset_id!r} is missing from catalog")

    lines: list[str] = []
    lines.append(f"[datasets.{dataset_id}]")
    for key, value in dataset_row.items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.append("")
    lines.append(f"[benchmarks.{benchmark_id}]")
    for key, value in benchmark_row.items():
        if key == "max_candidates_per_submission":
            lines.append("max_candidates_per_submission = 1")
            continue
        lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines)


def _render_search_space(benchmark_id: str) -> tuple[str, str]:
    source_payload = tomllib.loads(SOURCE_SEARCH_SPACE_PATH.read_text(encoding="utf-8"))
    source_payload["benchmark"] = benchmark_id
    search_space_id = f"mlp_{benchmark_id}_advisory_v1"
    source_payload["id"] = search_space_id

    lines: list[str] = [
        f'id = "{source_payload["id"]}"',
        f'benchmark = "{source_payload["benchmark"]}"',
        f'backend = "{source_payload["backend"]}"',
        f'model_family = "{source_payload["model_family"]}"',
        f'candidate_prefix = "{source_payload["candidate_prefix"]}"',
        "",
        "[defaults.preprocessing]",
    ]
    for key, value in source_payload["defaults"]["preprocessing"].items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.extend(["", "[defaults.resampling]"])
    for key, value in source_payload["defaults"]["resampling"].items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.extend(["", "[defaults.model]"])
    for key, value in source_payload["defaults"]["model"].items():
        lines.append(f"{key} = {_toml_value(value)}")

    for parameter in source_payload["parameters"]:
        lines.extend(["", "[[parameters]]"])
        for key, value in parameter.items():
            lines.append(f"{key} = {_toml_value(value)}")
    return search_space_id, "\n".join(lines)


def _write_policy(path: Path, spec: ExperimentSpec, search_space_relpath: str) -> None:
    if spec.mode == "agent":
        text = render_default_policy(agent_profile=spec.agent_profile or "01_ratchet").strip()
        lines = text.splitlines()
        if spec.advisors:
            lines[1] = f'agent_profile = "{spec.agent_profile}"'
            lines[2] = f'advisors = {json.dumps(list(spec.advisors))}'
            lines.append(f'search_space = "{search_space_relpath}"')
        _write_text(path, "\n".join(lines))
        return

    direct_lines = [
        'mode = "direct"',
        f'advisors = {json.dumps(list(spec.advisors))}',
        "proposal_count = 1",
        f'search_space = "{search_space_relpath}"',
    ]
    _write_text(path, "\n".join(direct_lines))


def _write_experiment_readme(root: Path, spec: ExperimentSpec, benchmark_id: str) -> None:
    advisors_label = ", ".join(spec.advisors) if spec.advisors else "-"
    lines = [
        f"# {spec.name}",
        "",
        f"- Condition: `{spec.condition_name}`",
        f"- Benchmark: `{benchmark_id}`",
        "- Model family: `mlp` only",
        "- Target rounds: `100`",
        "- Candidate policy: `exactly 1 candidate per run`",
        f"- Mode: `{spec.mode}`",
        f"- Advisors: `{advisors_label}`",
        f"- Agent profile: `{spec.agent_profile or '-'}`",
        "",
        "## Commands",
        "",
        f"- Advise: `./.venv/bin/python -m autoresearch advise --agent-dir agents/{spec.condition_name}`",
        f"- Run: `./.venv/bin/python -m autoresearch run --agent-dir agents/{spec.condition_name}`",
        f"- Finalize: `./.venv/bin/python -m autoresearch finalize-agent --agent-dir agents/{spec.condition_name}`",
        "",
        "## Isolation",
        "",
        "- This root contains a private `.work` and only one condition directory.",
        "- Do not inspect sibling experiment roots.",
        "- Use only local history, report, advice, leaderboard, and artifacts from this root.",
    ]
    _write_text(root / "EXPERIMENT.md", "\n".join(lines))


def _prepare_condition(root: Path, spec: ExperimentSpec, search_space_relpath: str) -> Path:
    agent_dir = root / "agents" / spec.condition_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    if spec.agent_profile is not None:
        _write_text(agent_dir / "program.md", render_program(spec.agent_profile, spec.condition_name))
    else:
        _write_text(
            agent_dir / "program.md",
            "# program.md\n\n- Direct condition. Use `advise` then `run` repeatedly for 100 rounds.\n",
        )
    _write_text(agent_dir / "submission.toml", DEFAULT_SUBMISSION)
    _write_policy(agent_dir / "policy.toml", spec, search_space_relpath)

    work_agent_dir = root / ".work" / "agents" / spec.condition_name
    _write_text(
        work_agent_dir / "history.md",
        "# History\n\n| run_id | benchmark | dataset | candidate | model | validation_score | rank | backend | mode | advisors | selection_origin | advice | artifact | run_best_candidate | run_best_validation | agent_best_candidate | agent_best_validation | dataset_model_best_agent | dataset_model_best_candidate | dataset_model_best_validation |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n",
    )
    _write_text(work_agent_dir / "report.md", "# Report\n\n")
    return agent_dir


def prepare_isolated_roots(benchmark_id: str, output_base: Path = OUTPUT_BASE) -> tuple[Path, list[dict[str, object]]]:
    base_root = output_base / TIMESTAMP / benchmark_id
    base_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []
    catalog_text = _render_subset_catalog(benchmark_id)
    search_space_id, search_space_text = _render_search_space(benchmark_id)
    search_space_name = f"{search_space_id}.toml"
    search_space_relpath = f"experiments/search_spaces/{search_space_name}"

    for spec in EXPERIMENT_SPECS:
        root = base_root / spec.name
        root.mkdir(parents=True, exist_ok=True)
        _copy_autoresearch_tree(REPO_ROOT / "autoresearch", root / "autoresearch")
        _ensure_symlink(root / ".venv", REPO_ROOT / ".venv")
        _ensure_symlink(root / "data", REPO_ROOT / "data")
        _write_text(root / "experiments" / "benchmark_catalog.toml", catalog_text)
        _write_text(root / "experiments" / "search_spaces" / search_space_name, search_space_text)
        agent_dir = _prepare_condition(root, spec, search_space_relpath)
        _write_experiment_readme(root, spec, benchmark_id)
        manifest_rows.append(
            {
                **asdict(spec),
                "root": str(root),
                "agent_dir": str(agent_dir),
                "rounds": 100,
                "benchmark": benchmark_id,
                "model_family": "mlp",
                "search_space_id": search_space_id,
            }
        )

    manifest_path = base_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_rows, indent=2), encoding="utf-8")
    return base_root, manifest_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare isolated 14-condition MLP advisory experiment roots.")
    parser.add_argument("--benchmark", required=True, help="Benchmark id from experiments/benchmark_catalog.toml.")
    parser.add_argument(
        "--output-base",
        default=str(OUTPUT_BASE),
        help="Parent directory for isolated batches. Default: /tmp/toy_research_isolated_experiments",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_root, manifest_rows = prepare_isolated_roots(
        benchmark_id=args.benchmark,
        output_base=Path(args.output_base),
    )
    print(f"base_root={base_root}")
    print(f"manifest={base_root / 'manifest.json'}")
    print(f"experiments={len(manifest_rows)}")
    for row in manifest_rows:
        print(f"{row['name']}\t{row['mode']}\t{','.join(row['advisors']) or '-'}\t{row['root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
