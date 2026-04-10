from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from autoresearch.agent_profiles import render_program
from autoresearch.policy import render_default_policy
from autoresearch.scaffold import DEFAULT_SUBMISSION


OUTPUT_BASE = Path("/tmp/toy_research_isolated_experiments")
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


CATALOG_TEXT = """[datasets.cifar10]
kind = "npz_classification"
path = "data/cifar10/cifar10.npz"
features_key = "x"
target_key = "y"
max_samples = 4000
sample_seed = 42
task = "classification"
description = "CIFAR-10 stored locally as npz and evaluated on a fixed 4k stratified subset."

[benchmarks.cifar10_real]
dataset = "cifar10"
metric = "accuracy"
backend = "sklearn"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["mlp"]
description = "Measured CIFAR-10 benchmark using a local npz."
"""


SEARCH_SPACE_TEXT = """id = "mlp_cifar10_advisory_v1"
benchmark = "cifar10_real"
backend = "sklearn"
model_family = "mlp"
candidate_prefix = "mlp"

[defaults.preprocessing]
normalization = "minmax"
outlier_strategy = "none"

[defaults.resampling]
strategy = "none"

[defaults.model]
hidden_dims = [64, 32]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64

[[parameters]]
path = "preprocessing.normalization"
type = "categorical"
choices = ["none", "minmax", "standard", "maxabs"]

[[parameters]]
path = "model.hidden_dims"
type = "categorical"
choices = [[32, 32], [64, 32], [64, 64], [128, 64]]

[[parameters]]
path = "model.activation"
type = "categorical"
choices = ["relu", "tanh", "gelu"]

[[parameters]]
path = "model.weight_decay"
type = "float"
low = 0.0001
high = 0.01
log = true

[[parameters]]
path = "model.learning_rate_init"
type = "float"
low = 0.0001
high = 0.01
log = true

[[parameters]]
path = "model.batch_size"
type = "categorical"
choices = [32, 64, 128]
"""


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


def _write_policy(path: Path, spec: ExperimentSpec) -> None:
    if spec.mode == "agent":
        text = render_default_policy(agent_profile=spec.agent_profile or "01_ratchet").strip()
        lines = text.splitlines()
        if spec.advisors:
            lines[1] = f'agent_profile = "{spec.agent_profile}"'
            lines[2] = f'advisors = {json.dumps(list(spec.advisors))}'
            lines.append('search_space = "experiments/search_spaces/mlp_cifar10_advisory_v1.toml"')
        _write_text(path, "\n".join(lines))
        return

    direct_lines = [
        'mode = "direct"',
        f'advisors = {json.dumps(list(spec.advisors))}',
        "proposal_count = 2",
        'search_space = "experiments/search_spaces/mlp_cifar10_advisory_v1.toml"',
    ]
    _write_text(path, "\n".join(direct_lines))


def _write_experiment_readme(root: Path, spec: ExperimentSpec) -> None:
    advisors_label = ", ".join(spec.advisors) if spec.advisors else "-"
    lines = [
        f"# {spec.name}",
        "",
        f"- Condition: `{spec.condition_name}`",
        "- Dataset: `cifar10_real`",
        "- Model family: `mlp` only",
        "- Target rounds: `100`",
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


def _prepare_condition(root: Path, spec: ExperimentSpec) -> Path:
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
    _write_policy(agent_dir / "policy.toml", spec)

    work_agent_dir = root / ".work" / "agents" / spec.condition_name
    _write_text(
        work_agent_dir / "history.md",
        "# History\n\n| run_id | benchmark | dataset | candidate | model | validation_score | rank | backend | mode | advisors | selection_origin | advice | artifact | run_best_candidate | run_best_validation | agent_best_candidate | agent_best_validation | dataset_model_best_agent | dataset_model_best_candidate | dataset_model_best_validation |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n",
    )
    _write_text(work_agent_dir / "report.md", "# Report\n\n")
    return agent_dir


def prepare_isolated_roots() -> tuple[Path, list[dict[str, object]]]:
    base_root = OUTPUT_BASE / TIMESTAMP
    base_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []

    for spec in EXPERIMENT_SPECS:
        root = base_root / spec.name
        root.mkdir(parents=True, exist_ok=True)
        _copy_autoresearch_tree(REPO_ROOT / "autoresearch", root / "autoresearch")
        _ensure_symlink(root / ".venv", REPO_ROOT / ".venv")
        _ensure_symlink(root / "data", REPO_ROOT / "data")
        _write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
        _write_text(root / "experiments" / "search_spaces" / "mlp_cifar10_advisory_v1.toml", SEARCH_SPACE_TEXT)
        agent_dir = _prepare_condition(root, spec)
        _write_experiment_readme(root, spec)
        manifest_rows.append(
            {
                **asdict(spec),
                "root": str(root),
                "agent_dir": str(agent_dir),
                "rounds": 100,
                "benchmark": "cifar10_real",
                "model_family": "mlp",
            }
        )

    manifest_path = base_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_rows, indent=2), encoding="utf-8")
    return base_root, manifest_rows


def main() -> int:
    base_root, manifest_rows = prepare_isolated_roots()
    print(f"base_root={base_root}")
    print(f"manifest={base_root / 'manifest.json'}")
    print(f"experiments={len(manifest_rows)}")
    for row in manifest_rows:
        print(f"{row['name']}\t{row['mode']}\t{','.join(row['advisors']) or '-'}\t{row['root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
