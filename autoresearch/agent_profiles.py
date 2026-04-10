from __future__ import annotations

from pathlib import Path


DEFAULT_AGENT_PROFILE = "01_ratchet"


_PROFILE_ALIASES = {
    "01": "01_ratchet",
    "01_ratchet": "01_ratchet",
    "ratchet": "01_ratchet",
    "exploit": "01_ratchet",
    "02": "02_screening_doe",
    "02_screening_doe": "02_screening_doe",
    "screening": "02_screening_doe",
    "explore": "02_screening_doe",
    "03": "03_advanced_doe",
    "03_advanced_doe": "03_advanced_doe",
    "advanced": "03_advanced_doe",
    "ablation": "03_advanced_doe",
}


_PROFILE_SECTIONS = {
    "01_ratchet": {
        "initial": (
            "Read `autoresearch/backends.py` once when starting the run.",
            "If repo-native MLP controls may matter, also read `autoresearch/repo_mlp.py` once.",
            "If `policy.toml` enables advisors, run `python3 -m autoresearch advise --agent-dir agents/{agent_name}` and read `.work/agents/{agent_name}/advice/latest.md`.",
            "Read `.work/agents/{agent_name}/history.md`, `.work/agents/{agent_name}/report.md`, and `agents/{agent_name}/submission.toml` before starting.",
        ),
        "initial_commands": (
            "`cat autoresearch/backends.py`",
            "Optional: `cat autoresearch/repo_mlp.py`",
            "Optional: `python3 -m autoresearch advise --agent-dir agents/{agent_name}`",
            "Optional: `cat .work/agents/{agent_name}/advice/latest.md`",
            "`cat .work/agents/{agent_name}/history.md`",
            "`cat .work/agents/{agent_name}/report.md`",
            "`cat agents/{agent_name}/submission.toml`",
        ),
        "loop": (
            "Read `history.md` and `report.md` before each round.",
            "If advisors are enabled, refresh `advice/latest.md` before editing `submission.toml`.",
            "Treat advisor recommendations as guidance, not as mandatory submissions; you may adapt, combine, or replace them with a novel config.",
            "Edit `submission.toml` for one small mutation around the current incumbent.",
            "Submit one round and read the updated `history.md`.",
            "Append a `## Run <run_id>` section to `report.md` with `Change: ...`, `Interpretation: ...`, `Decision: ...`, and `Next: ...`.",
            "Keep or discard the idea, then repeat as long as the run continues.",
            "Reveal hidden test only when ending the agent.",
        ),
        "loop_commands": (
            "Optional: `python3 -m autoresearch advise --agent-dir agents/{agent_name}`",
            "Optional: `cat .work/agents/{agent_name}/advice/latest.md`",
            "`cat .work/agents/{agent_name}/history.md`",
            "`cat .work/agents/{agent_name}/report.md`",
            "Edit `agents/{agent_name}/submission.toml`",
            "`python3 -m autoresearch run --agent-dir agents/{agent_name}`",
            "`cat .work/agents/{agent_name}/history.md`",
            "Append the new run section to `.work/agents/{agent_name}/report.md`",
            "`python3 -m autoresearch finalize-agent --agent-dir agents/{agent_name}` only when ending the agent",
        ),
        "search_strategy": (
            "Start with a baseline if the history is empty.",
            "Treat the best validated candidate as the incumbent.",
            "Use each round as a tight keep-or-discard mutation around that incumbent.",
            "Prefer one primary mutation per run and queue nearby ablations, simplifications, or safer variants for later rounds.",
            "If the current neighborhood stalls, jump to a materially different idea.",
        ),
    },
    "02_screening_doe": {
        "initial": (
            "Read `autoresearch/backends.py` once when starting the run.",
            "If repo-native MLP controls may matter, also read `autoresearch/repo_mlp.py` once.",
            "If `policy.toml` enables advisors, run `python3 -m autoresearch advise --agent-dir agents/{agent_name}` and read `.work/agents/{agent_name}/advice/latest.md`.",
            "Read `.work/agents/{agent_name}/history.md`, `.work/agents/{agent_name}/report.md`, and `agents/{agent_name}/submission.toml` before starting.",
        ),
        "initial_commands": (
            "`cat autoresearch/backends.py`",
            "Optional: `cat autoresearch/repo_mlp.py`",
            "Optional: `python3 -m autoresearch advise --agent-dir agents/{agent_name}`",
            "Optional: `cat .work/agents/{agent_name}/advice/latest.md`",
            "`cat .work/agents/{agent_name}/history.md`",
            "`cat .work/agents/{agent_name}/report.md`",
            "`cat agents/{agent_name}/submission.toml`",
        ),
        "loop": (
            "Read `history.md` and `report.md` before each round.",
            "If advisors are enabled, refresh `advice/latest.md` before choosing the next screening contrast.",
            "Treat advisor recommendations as guidance, not as mandatory submissions; you may adapt, combine, or replace them with a novel config.",
            "Edit `submission.toml` to answer one screening question.",
            "Submit one round and read the updated `history.md`.",
            "Append a `## Run <run_id>` section to `report.md` with `Hypothesis: ...`, `Factors: ...`, `Levels: ...`, `Interpretation: ...`, `Decision: ...`, and `Next: ...`.",
            "Choose the next contrast, then repeat as long as the run continues.",
            "Reveal hidden test only when ending the agent.",
        ),
        "loop_commands": (
            "Optional: `python3 -m autoresearch advise --agent-dir agents/{agent_name}`",
            "Optional: `cat .work/agents/{agent_name}/advice/latest.md`",
            "`cat .work/agents/{agent_name}/history.md`",
            "`cat .work/agents/{agent_name}/report.md`",
            "Edit `agents/{agent_name}/submission.toml`",
            "`python3 -m autoresearch run --agent-dir agents/{agent_name}`",
            "`cat .work/agents/{agent_name}/history.md`",
            "Append the new run section to `.work/agents/{agent_name}/report.md`",
            "`python3 -m autoresearch finalize-agent --agent-dir agents/{agent_name}` only when ending the agent",
        ),
        "search_strategy": (
            "Treat each round as one clean screening question.",
            "Use one candidate per run and compare anchor versus treatment sequentially through `history.md` instead of expecting two candidate slots.",
            "Start broad across factor groups before doing local tuning.",
            "Hold nuisance factors fixed so the main effect stays attributable.",
            "If the current screening path stalls, reopen screening on neglected factors or a new anchor region.",
        ),
    },
    "03_advanced_doe": {
        "initial": (
            "Read `autoresearch/backends.py` once when starting the run.",
            "If repo-native MLP controls may matter, also read `autoresearch/repo_mlp.py` once.",
            "If `policy.toml` enables advisors, run `python3 -m autoresearch advise --agent-dir agents/{agent_name}` and read `.work/agents/{agent_name}/advice/latest.md`.",
            "Read `.work/agents/{agent_name}/history.md`, `.work/agents/{agent_name}/report.md`, and `agents/{agent_name}/submission.toml` before starting.",
        ),
        "initial_commands": (
            "`cat autoresearch/backends.py`",
            "Optional: `cat autoresearch/repo_mlp.py`",
            "Optional: `python3 -m autoresearch advise --agent-dir agents/{agent_name}`",
            "Optional: `cat .work/agents/{agent_name}/advice/latest.md`",
            "`cat .work/agents/{agent_name}/history.md`",
            "`cat .work/agents/{agent_name}/report.md`",
            "`cat agents/{agent_name}/submission.toml`",
        ),
        "loop": (
            "Read `history.md` and `report.md` before each round and reconstruct the DOE state from both.",
            "If advisors are enabled, refresh `advice/latest.md` before choosing the next design question.",
            "Treat advisor recommendations as guidance, not as mandatory submissions; you may adapt, combine, or replace them with a novel config.",
            "Edit `submission.toml` for one design question.",
            "Submit one round and read the updated `history.md`.",
            "Append a `## Run <run_id>` section to `report.md` in this exact shape: `Stage: ...; Anchor: ...; Question: ...; Factors: ...; Levels: ...; Alias risk: ...; Prediction: ...; Observed signal: ...; Belief: ...; Decision: ...; Next: ...`",
            "Update the staged DOE plan, then repeat as long as the run continues.",
            "Reveal hidden test only when ending the agent.",
        ),
        "loop_commands": (
            "Optional: `python3 -m autoresearch advise --agent-dir agents/{agent_name}`",
            "Optional: `cat .work/agents/{agent_name}/advice/latest.md`",
            "`cat .work/agents/{agent_name}/history.md`",
            "`cat .work/agents/{agent_name}/report.md`",
            "Edit `agents/{agent_name}/submission.toml`",
            "`python3 -m autoresearch run --agent-dir agents/{agent_name}`",
            "`cat .work/agents/{agent_name}/history.md`",
            "Append the new run section to `.work/agents/{agent_name}/report.md`",
            "`python3 -m autoresearch finalize-agent --agent-dir agents/{agent_name}` only when ending the agent",
        ),
        "search_strategy": (
            "Run a staged DOE program: screening, then interaction checks, then local refinement.",
            "Use one candidate for the current anchor-or-treatment question and compare against prior rounds instead of expecting two fresh points in one run.",
            "Prefer contrasts that separate effects cleanly and use foldover or orthogonal follow-up when a result is aliased or ambiguous.",
            "Spend later rounds only on factors that showed evidence during screening.",
            "If the current DOE path stalls, reopen screening, run a deliberate interaction check, or reset around a different anchor.",
        ),
    },
}


CLI_AGENT_PROFILE_CHOICES = (
    "01",
    "02",
    "03",
    "01_ratchet",
    "02_screening_doe",
    "03_advanced_doe",
    "exploit",
    "explore",
    "ablation",
)


def normalize_agent_profile(raw: str | None, default: str = DEFAULT_AGENT_PROFILE) -> str:
    value = (raw or "").strip()
    if not value:
        return default
    try:
        return _PROFILE_ALIASES[value]
    except KeyError as exc:
        supported = ", ".join(sorted({"01", "02", "03", *list(_PROFILE_SECTIONS.keys())}))
        raise ValueError(f"Unknown agent profile {value!r}. Supported values: {supported}.") from exc


def render_program(agent_profile: str, agent_name: str) -> str:
    profile = _PROFILE_SECTIONS[normalize_agent_profile(agent_profile)]
    rendered_sections = ["# program.md", ""]
    for title, key in (
        ("Initial", "initial"),
        ("Initial Commands", "initial_commands"),
        ("Loop", "loop"),
        ("Loop Commands", "loop_commands"),
        ("Search Strategy", "search_strategy"),
    ):
        rendered_sections.append(f"## {title}")
        rendered_sections.append("")
        items = profile[key]
        for index, item in enumerate(items, start=1):
            text = item.format(agent_name=agent_name)
            prefix = f"{index}. " if "Commands" in title else "- "
            rendered_sections.append(f"{prefix}{text}")
        rendered_sections.append("")
    return "\n".join(rendered_sections).rstrip() + "\n"


def materialize_program(agent_dir: Path, agent_profile: str) -> Path:
    path = Path(agent_dir) / "program.md"
    path.write_text(render_program(agent_profile, Path(agent_dir).name), encoding="utf-8")
    return path
