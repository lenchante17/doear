from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import copy
import tomllib

from autoresearch.domain import CandidateConfig


class SearchSpaceLoadError(ValueError):
    pass


@dataclass(frozen=True)
class SearchParameterSpec:
    path: str
    parameter_type: str
    choices: tuple[Any, ...] = ()
    low: float | int | None = None
    high: float | int | None = None
    log: bool = False
    step: float | int | None = None


@dataclass(frozen=True)
class SearchSpaceSpec:
    search_space_id: str
    benchmark_id: str
    backend: str
    model_family: str
    candidate_prefix: str
    defaults_preprocessing: dict[str, Any]
    defaults_resampling: dict[str, Any]
    defaults_model: dict[str, Any]
    parameters: tuple[SearchParameterSpec, ...]
    source_path: Path


def _deep_copy_dict(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)


def _get_nested(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _set_nested(payload: dict[str, Any], dotted_path: str, value: Any) -> None:
    current = payload
    segments = dotted_path.split(".")
    for segment in segments[:-1]:
        current = current.setdefault(segment, {})
    current[segments[-1]] = value


def load_search_space(path: Path) -> SearchSpaceSpec:
    path = Path(path)
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    required = {"id", "benchmark", "backend", "model_family"}
    missing = sorted(key for key in required if not str(raw.get(key, "")).strip())
    if missing:
        raise SearchSpaceLoadError(f"Search space {path} is missing required keys {missing}.")

    defaults = raw.get("defaults", {})
    if defaults and not isinstance(defaults, dict):
        raise SearchSpaceLoadError("Search space defaults must be a table.")
    defaults = defaults if isinstance(defaults, dict) else {}

    parameters_raw = raw.get("parameters", [])
    if not isinstance(parameters_raw, list) or not parameters_raw:
        raise SearchSpaceLoadError("Search space must define at least one [[parameters]] block.")

    parameters: list[SearchParameterSpec] = []
    for item in parameters_raw:
        if not isinstance(item, dict):
            raise SearchSpaceLoadError("Search space parameter blocks must be tables.")
        dotted_path = str(item.get("path", "")).strip()
        parameter_type = str(item.get("type", "")).strip()
        if not dotted_path or not parameter_type:
            raise SearchSpaceLoadError("Each parameter must define path and type.")
        if parameter_type not in {"categorical", "float", "int", "bool"}:
            raise SearchSpaceLoadError(f"Unsupported parameter type {parameter_type!r}.")
        choices: tuple[Any, ...] = ()
        low: float | int | None = None
        high: float | int | None = None
        if parameter_type == "categorical":
            raw_choices = item.get("choices")
            if not isinstance(raw_choices, list) or not raw_choices:
                raise SearchSpaceLoadError(f"Categorical parameter {dotted_path!r} must define choices.")
            choices = tuple(raw_choices)
        elif parameter_type == "bool":
            choices = (False, True)
        else:
            if "low" not in item or "high" not in item:
                raise SearchSpaceLoadError(f"Numeric parameter {dotted_path!r} must define low/high.")
            low = item["low"]
            high = item["high"]
        parameters.append(
            SearchParameterSpec(
                path=dotted_path,
                parameter_type=parameter_type,
                choices=choices,
                low=low,
                high=high,
                log=bool(item.get("log", False)),
                step=item.get("step"),
            )
        )

    return SearchSpaceSpec(
        search_space_id=str(raw["id"]),
        benchmark_id=str(raw["benchmark"]),
        backend=str(raw["backend"]),
        model_family=str(raw["model_family"]),
        candidate_prefix=str(raw.get("candidate_prefix", raw["model_family"])),
        defaults_preprocessing=_deep_copy_dict(defaults.get("preprocessing", {})),
        defaults_resampling=_deep_copy_dict(defaults.get("resampling", {})),
        defaults_model=_deep_copy_dict(defaults.get("model", {})),
        parameters=tuple(parameters),
        source_path=path,
    )


def candidate_from_parameter_values(
    search_space: SearchSpaceSpec,
    sampled_values: dict[str, Any],
    candidate_name: str,
) -> CandidateConfig:
    candidate = {
        "preprocessing": _deep_copy_dict(search_space.defaults_preprocessing),
        "resampling": _deep_copy_dict(search_space.defaults_resampling),
        "model": _deep_copy_dict(search_space.defaults_model),
    }
    for parameter in search_space.parameters:
        if parameter.path in sampled_values:
            _set_nested(candidate, parameter.path, sampled_values[parameter.path])

    return CandidateConfig(
        name=candidate_name,
        model_family=search_space.model_family,
        preprocessing=candidate["preprocessing"],
        resampling=candidate["resampling"],
        model=candidate["model"],
    )


def candidate_to_parameter_values(
    search_space: SearchSpaceSpec,
    candidate: CandidateConfig,
) -> dict[str, Any]:
    payload = {
        "preprocessing": candidate.preprocessing,
        "resampling": candidate.resampling,
        "model": candidate.model,
    }
    flattened: dict[str, Any] = {}
    for parameter in search_space.parameters:
        value = _get_nested(payload, parameter.path)
        if value is None:
            value = _get_nested(
                {
                    "preprocessing": search_space.defaults_preprocessing,
                    "resampling": search_space.defaults_resampling,
                    "model": search_space.defaults_model,
                },
                parameter.path,
            )
        flattened[parameter.path] = value
    return flattened
