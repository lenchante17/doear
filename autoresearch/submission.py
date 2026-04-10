from __future__ import annotations

from pathlib import Path
import json
import tomllib

from autoresearch.domain import CandidateConfig, Submission


class SubmissionLoadError(ValueError):
    pass


def _as_dict(value: object, path: Path, field_name: str, candidate_name: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SubmissionLoadError(
            f"Candidate {candidate_name!r} in {path} must define {field_name} as a table."
        )
    return {str(key): item for key, item in value.items()}


def load_submission(path: Path) -> Submission:
    path = Path(path)
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    unsupported_top_level = sorted(set(raw) - {"benchmark", "backend", "candidates"})
    if unsupported_top_level:
        raise SubmissionLoadError(
            f"Submission {path} contains unsupported top-level keys {unsupported_top_level}. "
            "Put narrative experiment notes in `.work/agents/<agent_name>/report.md` instead."
        )

    benchmark_id = str(raw.get("benchmark", "")).strip()
    if not benchmark_id:
        raise SubmissionLoadError(f"Submission {path} is missing a benchmark identifier.")

    backend = str(raw.get("backend", "")).strip() or "stub"
    raw_candidates = raw.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise SubmissionLoadError(f"Submission {path} must define at least one [[candidates]] block.")

    candidates: list[CandidateConfig] = []
    for index, candidate_raw in enumerate(raw_candidates, start=1):
        if not isinstance(candidate_raw, dict):
            raise SubmissionLoadError(f"Candidate #{index} in {path} must be a TOML table.")
        name = str(candidate_raw.get("name", "")).strip()
        family = str(candidate_raw.get("model_family", "")).strip()
        if not name or not family:
            raise SubmissionLoadError(
                f"Candidate #{index} in {path} must define both name and model_family."
            )
        preprocessing = _as_dict(candidate_raw.get("preprocessing"), path, "preprocessing", name)
        resampling = _as_dict(candidate_raw.get("resampling"), path, "resampling", name)
        model = _as_dict(candidate_raw.get("model"), path, "model", name)
        candidates.append(
            CandidateConfig(
                name=name,
                model_family=family,
                preprocessing=preprocessing,
                resampling=resampling,
                model=model,
            )
        )

    return Submission(
        benchmark_id=benchmark_id,
        backend=backend,
        candidates=tuple(candidates),
        source_path=path,
    )


def render_submission(submission: Submission) -> str:
    def _format_toml_value(value: object) -> str:
        if hasattr(value, "tolist"):
            converted = value.tolist()
            if converted is not value:
                return _format_toml_value(converted)
        if hasattr(value, "item"):
            try:
                converted = value.item()
            except (TypeError, ValueError):
                converted = value
            if converted is not value:
                return _format_toml_value(converted)
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, list):
            return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
        raise SubmissionLoadError(f"Unsupported TOML value type for generated submission: {type(value)!r}")

    lines = [
        f'benchmark = "{submission.benchmark_id}"',
        f'backend = "{submission.backend}"',
        "",
    ]
    for candidate in submission.candidates:
        lines.extend(
            [
                "[[candidates]]",
                f'name = "{candidate.name}"',
                f'model_family = "{candidate.model_family}"',
            ]
        )
        for section_name, payload in (
            ("preprocessing", candidate.preprocessing),
            ("resampling", candidate.resampling),
            ("model", candidate.model),
        ):
            lines.append(f"[candidates.{section_name}]")
            for key, value in payload.items():
                lines.append(f"{key} = {_format_toml_value(value)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_submission(path: Path, submission: Submission) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_submission(submission), encoding="utf-8")
    return path
