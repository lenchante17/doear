from __future__ import annotations

from pathlib import Path


WORK_DIRNAME = ".work"


def _agent_name(agent_name_or_dir: str | Path) -> str:
    return Path(agent_name_or_dir).name


def work_dir(root: Path) -> Path:
    return Path(root) / WORK_DIRNAME


def runs_dir(root: Path) -> Path:
    return work_dir(root) / "runs"


def finalized_dir(root: Path) -> Path:
    return work_dir(root) / "finalized"


def leaderboard_path(root: Path) -> Path:
    return work_dir(root) / "leaderboard.md"


def agent_runtime_dir(root: Path, agent_name_or_dir: str | Path) -> Path:
    return work_dir(root) / "agents" / _agent_name(agent_name_or_dir)


def history_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return agent_runtime_dir(root, agent_name_or_dir) / "history.md"


def final_report_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return agent_runtime_dir(root, agent_name_or_dir) / "final_report.md"


def report_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return agent_runtime_dir(root, agent_name_or_dir) / "report.md"


def advice_dir(root: Path, agent_name_or_dir: str | Path) -> Path:
    return agent_runtime_dir(root, agent_name_or_dir) / "advice"


def advice_latest_summary_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return advice_dir(root, agent_name_or_dir) / "latest.md"


def advice_current_session_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return advice_dir(root, agent_name_or_dir) / "current.json"


def advice_session_snapshot_path(root: Path, agent_name_or_dir: str | Path, session_id: str, advisor_name: str) -> Path:
    return advice_dir(root, agent_name_or_dir) / f"{session_id}__{advisor_name}.json"


def advice_used_session_path(root: Path, agent_name_or_dir: str | Path, run_id: str) -> Path:
    return advice_dir(root, agent_name_or_dir) / "used" / f"{run_id}.json"


def sequence_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return agent_runtime_dir(root, agent_name_or_dir) / "sequence.md"


def public_artifact_path(root: Path, run_id: str) -> Path:
    return runs_dir(root) / f"{run_id}.json"


def finalized_artifact_path(root: Path, agent_name_or_dir: str | Path) -> Path:
    return finalized_dir(root) / f"{_agent_name(agent_name_or_dir)}.json"
