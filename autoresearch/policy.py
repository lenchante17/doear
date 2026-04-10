from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from autoresearch.agent_profiles import DEFAULT_AGENT_PROFILE, normalize_agent_profile


class PolicyLoadError(ValueError):
    pass


ALLOWED_POLICY_MODES = {"agent", "direct"}
ALLOWED_ADVISORS = {"optuna_tpe", "smac3"}


@dataclass(frozen=True)
class PolicySpec:
    mode: str = "agent"
    agent_profile: str = DEFAULT_AGENT_PROFILE
    advisors: tuple[str, ...] = ()
    proposal_count: int = 2
    search_space_path: Path | None = None
    source_path: Path | None = None


DEFAULT_POLICY = """mode = "agent"
agent_profile = "{agent_profile}"
advisors = []
proposal_count = 2
"""


def render_default_policy(agent_profile: str = DEFAULT_AGENT_PROFILE) -> str:
    normalized = normalize_agent_profile(agent_profile)
    return DEFAULT_POLICY.format(agent_profile=normalized)


def load_policy(root: Path, agent_dir: Path) -> PolicySpec:
    root = Path(root)
    agent_dir = Path(agent_dir)
    path = agent_dir / "policy.toml"
    if not path.exists():
        return PolicySpec(source_path=path)

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    unknown = sorted(set(raw) - {"mode", "agent_profile", "advisors", "proposal_count", "search_space"})
    if unknown:
        raise PolicyLoadError(f"Policy {path} contains unsupported keys {unknown}.")

    mode = str(raw.get("mode", "agent")).strip() or "agent"
    if mode not in ALLOWED_POLICY_MODES:
        raise PolicyLoadError(f"Policy mode must be one of {sorted(ALLOWED_POLICY_MODES)}.")

    try:
        agent_profile = normalize_agent_profile(
            str(raw.get("agent_profile", DEFAULT_AGENT_PROFILE if mode == "agent" else "")).strip(),
            default=DEFAULT_AGENT_PROFILE,
        )
    except ValueError as exc:
        raise PolicyLoadError(str(exc)) from exc

    raw_advisors = raw.get("advisors", [])
    if not isinstance(raw_advisors, list):
        raise PolicyLoadError("Policy advisors must be an array.")
    advisors = tuple(str(item).strip() for item in raw_advisors if str(item).strip())
    unknown_advisors = sorted(set(advisors) - ALLOWED_ADVISORS)
    if unknown_advisors:
        raise PolicyLoadError(
            f"Policy advisors must be drawn from {sorted(ALLOWED_ADVISORS)}; got {unknown_advisors}."
        )

    proposal_count = int(raw.get("proposal_count", 2))
    if proposal_count <= 0:
        raise PolicyLoadError("Policy proposal_count must be positive.")

    search_space_path: Path | None = None
    raw_search_space = str(raw.get("search_space", "")).strip()
    if raw_search_space:
        search_space_path = Path(raw_search_space)
        if not search_space_path.is_absolute():
            search_space_path = (root / search_space_path).resolve()

    if advisors and search_space_path is None:
        raise PolicyLoadError("Policies with advisors must define search_space.")
    if mode == "direct" and not advisors:
        raise PolicyLoadError("Direct policies require at least one advisor.")
    if mode == "direct" and str(raw.get("agent_profile", "")).strip():
        raise PolicyLoadError("Direct policies do not accept agent_profile.")

    return PolicySpec(
        mode=mode,
        agent_profile=agent_profile,
        advisors=advisors,
        proposal_count=proposal_count,
        search_space_path=search_space_path,
        source_path=path,
    )
