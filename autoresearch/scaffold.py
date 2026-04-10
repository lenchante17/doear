from __future__ import annotations

from pathlib import Path

from autoresearch.agent_report import ensure_report_file
from autoresearch.agent_profiles import DEFAULT_AGENT_PROFILE, materialize_program, normalize_agent_profile
from autoresearch.history import ensure_history_header
from autoresearch.policy import render_default_policy


DEFAULT_SUBMISSION = """benchmark = "cifar10_real"
backend = "sklearn"

[[candidates]]
name = "mlp_baseline"
model_family = "mlp"
[candidates.preprocessing]
normalization = "minmax"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
"""


def scaffold_agent(root: Path, agent_name: str, strategy: str) -> Path:
    try:
        normalized_profile = normalize_agent_profile(strategy, default=DEFAULT_AGENT_PROFILE)
    except ValueError:
        normalized_profile = DEFAULT_AGENT_PROFILE
    agent_dir = root / "agents" / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)

    materialize_program(agent_dir, normalized_profile)
    (agent_dir / "submission.toml").write_text(DEFAULT_SUBMISSION, encoding="utf-8")
    (agent_dir / "policy.toml").write_text(
        render_default_policy(agent_profile=normalized_profile),
        encoding="utf-8",
    )
    ensure_history_header(root, agent_dir)
    ensure_report_file(root, agent_dir)
    return agent_dir
