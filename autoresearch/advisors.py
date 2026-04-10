from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
from typing import Any, Callable

from autoresearch.domain import CandidateConfig
from autoresearch.search_space import (
    SearchParameterSpec,
    SearchSpaceSpec,
    candidate_from_parameter_values,
    candidate_to_parameter_values,
)


class AdvisorError(RuntimeError):
    pass


class AdvisorDependencyError(AdvisorError):
    pass


@dataclass(frozen=True)
class HistoryObservation:
    run_id: str
    candidate: CandidateConfig
    validation_score: float


@dataclass(frozen=True)
class AdvisorRecommendation:
    rank: int
    candidate: CandidateConfig
    rationale: str = ""


@dataclass(frozen=True)
class AdvisorSnapshot:
    advisor_name: str
    search_space_id: str
    history_run_ids: tuple[str, ...]
    recommendations: tuple[AdvisorRecommendation, ...]


AdvisorFactory = Callable[[SearchSpaceSpec, list[HistoryObservation], int, int], AdvisorSnapshot]


def _parameter_signature(search_space: SearchSpaceSpec, candidate: CandidateConfig) -> str:
    return json.dumps(
        _json_safe(candidate_to_parameter_values(search_space, candidate)),
        sort_keys=True,
    )


def _sample_fallback_value(rng: random.Random, parameter: SearchParameterSpec) -> Any:
    if parameter.parameter_type == "categorical":
        return rng.choice(list(parameter.choices))
    if parameter.parameter_type == "bool":
        return rng.choice([False, True])
    if parameter.parameter_type == "int":
        low = int(parameter.low)
        high = int(parameter.high)
        if parameter.log:
            sampled = int(round(math.exp(rng.uniform(math.log(low), math.log(high)))))
        else:
            sampled = rng.randint(low, high)
        if parameter.step is not None:
            step = int(parameter.step)
            sampled = low + round((sampled - low) / step) * step
        return max(low, min(high, sampled))
    if parameter.parameter_type == "float":
        low = float(parameter.low)
        high = float(parameter.high)
        if parameter.log:
            sampled = math.exp(rng.uniform(math.log(low), math.log(high)))
        else:
            sampled = rng.uniform(low, high)
        if parameter.step is not None:
            step = float(parameter.step)
            sampled = low + round((sampled - low) / step) * step
        return max(low, min(high, sampled))
    raise AdvisorError(f"Unsupported fallback parameter type {parameter.parameter_type!r}.")


def _append_fallback_recommendations(
    search_space: SearchSpaceSpec,
    recommendations: list[AdvisorRecommendation],
    seen_signatures: set[str],
    proposal_count: int,
    seed: int,
    advisor_name: str,
) -> None:
    rng = random.Random((seed + 1) * 9973 + len(seen_signatures))
    attempts = 0
    max_attempts = max(proposal_count * 200, 200)
    while len(recommendations) < proposal_count and attempts < max_attempts:
        attempts += 1
        sampled = {
            parameter.path: _sample_fallback_value(rng, parameter)
            for parameter in search_space.parameters
        }
        candidate = candidate_from_parameter_values(
            search_space,
            sampled,
            candidate_name=f"{search_space.candidate_prefix}_{advisor_name}_{len(recommendations) + 1}",
        )
        signature = _parameter_signature(search_space, candidate)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        recommendations.append(
            AdvisorRecommendation(
                rank=len(recommendations) + 1,
                candidate=candidate,
                rationale=(
                    f"{advisor_name} fallback recommendation after repeated duplicate proposals in current history."
                ),
            )
        )


def _optuna_distribution(parameter: SearchParameterSpec) -> Any:
    import optuna

    if parameter.parameter_type == "categorical":
        return optuna.distributions.CategoricalDistribution(choices=parameter.choices)
    if parameter.parameter_type == "bool":
        return optuna.distributions.CategoricalDistribution(choices=[False, True])
    if parameter.parameter_type == "int":
        return optuna.distributions.IntDistribution(
            low=int(parameter.low),
            high=int(parameter.high),
            log=parameter.log,
            step=int(parameter.step) if parameter.step is not None else 1,
        )
    if parameter.parameter_type == "float":
        return optuna.distributions.FloatDistribution(
            low=float(parameter.low),
            high=float(parameter.high),
            log=parameter.log,
            step=float(parameter.step) if parameter.step is not None else None,
        )
    raise AdvisorError(f"Unsupported Optuna parameter type {parameter.parameter_type!r}.")


def _sample_optuna_value(trial: Any, parameter: SearchParameterSpec) -> Any:
    if parameter.parameter_type == "categorical":
        return trial.suggest_categorical(parameter.path, list(parameter.choices))
    if parameter.parameter_type == "bool":
        return trial.suggest_categorical(parameter.path, [False, True])
    if parameter.parameter_type == "int":
        kwargs = {"log": parameter.log}
        if parameter.step is not None:
            kwargs["step"] = int(parameter.step)
        return trial.suggest_int(parameter.path, int(parameter.low), int(parameter.high), **kwargs)
    if parameter.parameter_type == "float":
        kwargs = {"log": parameter.log}
        if parameter.step is not None:
            kwargs["step"] = float(parameter.step)
        return trial.suggest_float(parameter.path, float(parameter.low), float(parameter.high), **kwargs)
    raise AdvisorError(f"Unsupported Optuna parameter type {parameter.parameter_type!r}.")


def recommend_with_optuna(
    search_space: SearchSpaceSpec,
    history_rows: list[HistoryObservation],
    proposal_count: int,
    seed: int,
) -> AdvisorSnapshot:
    try:
        import optuna
    except ModuleNotFoundError as exc:
        raise AdvisorDependencyError(
            "optuna_tpe advisory requires the optional 'optuna' dependency."
        ) from exc

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    distributions = {
        parameter.path: _optuna_distribution(parameter)
        for parameter in search_space.parameters
    }
    seen_signatures = {_parameter_signature(search_space, row.candidate) for row in history_rows}
    for row in history_rows:
        params = candidate_to_parameter_values(search_space, row.candidate)
        try:
            trial = optuna.trial.create_trial(
                params=params,
                distributions=distributions,
                value=float(row.validation_score),
            )
        except ValueError:
            continue
        study.add_trial(trial)

    recommendations: list[AdvisorRecommendation] = []
    attempts = 0
    max_attempts = max(proposal_count * 20, 50)
    while len(recommendations) < proposal_count and attempts < max_attempts:
        attempts += 1
        trial = study.ask()
        sampled = {
            parameter.path: _sample_optuna_value(trial, parameter)
            for parameter in search_space.parameters
        }
        candidate = candidate_from_parameter_values(
            search_space,
            sampled,
            candidate_name=f"{search_space.candidate_prefix}_optuna_tpe_{len(recommendations) + 1}",
        )
        signature = _parameter_signature(search_space, candidate)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        recommendations.append(
            AdvisorRecommendation(
                rank=len(recommendations) + 1,
                candidate=candidate,
                rationale="Optuna TPE recommendation from current condition history.",
            )
        )
    if len(recommendations) < proposal_count:
        _append_fallback_recommendations(
            search_space,
            recommendations,
            seen_signatures,
            proposal_count,
            seed,
            advisor_name="optuna_tpe",
        )

    return AdvisorSnapshot(
        advisor_name="optuna_tpe",
        search_space_id=search_space.search_space_id,
        history_run_ids=tuple(row.run_id for row in history_rows),
        recommendations=tuple(recommendations),
    )


def _build_configspace(search_space: SearchSpaceSpec) -> Any:
    from ConfigSpace import Categorical, ConfigurationSpace, Float, Integer

    config_space = ConfigurationSpace(seed=0)
    hyperparameters = []
    for parameter in search_space.parameters:
        if parameter.parameter_type == "categorical":
            hyperparameters.append(Categorical(parameter.path, list(parameter.choices)))
        elif parameter.parameter_type == "bool":
            hyperparameters.append(Categorical(parameter.path, [False, True]))
        elif parameter.parameter_type == "int":
            hyperparameters.append(
                Integer(
                    parameter.path,
                    (int(parameter.low), int(parameter.high)),
                    log=parameter.log,
                )
            )
        elif parameter.parameter_type == "float":
            hyperparameters.append(
                Float(
                    parameter.path,
                    (float(parameter.low), float(parameter.high)),
                    log=parameter.log,
                )
            )
        else:
            raise AdvisorError(f"Unsupported SMAC3 parameter type {parameter.parameter_type!r}.")
    config_space.add(hyperparameters)
    return config_space


def recommend_with_smac3(
    search_space: SearchSpaceSpec,
    history_rows: list[HistoryObservation],
    proposal_count: int,
    seed: int,
) -> AdvisorSnapshot:
    try:
        from ConfigSpace.exceptions import IllegalValueError
        from smac import HyperparameterOptimizationFacade, Scenario
        from smac.runhistory.dataclasses import TrialInfo, TrialValue
    except ModuleNotFoundError as exc:
        raise AdvisorDependencyError(
            "smac3 advisory requires optional 'smac' and 'ConfigSpace' dependencies."
        ) from exc

    config_space = _build_configspace(search_space)
    scenario = Scenario(configspace=config_space, deterministic=True, n_trials=max(1, proposal_count + len(history_rows)), seed=seed)

    def _target_function(config: Any, seed: int = 0) -> float:
        return 0.0

    smac = HyperparameterOptimizationFacade(scenario, _target_function, overwrite=True)
    seen_signatures = {_parameter_signature(search_space, row.candidate) for row in history_rows}

    for row in history_rows:
        config = config_space.get_default_configuration()
        try:
            for key, value in candidate_to_parameter_values(search_space, row.candidate).items():
                config[key] = value
            smac.tell(TrialInfo(config=config, seed=seed), TrialValue(cost=1.0 - float(row.validation_score)))
        except (IllegalValueError, ValueError, TypeError):
            continue

    recommendations: list[AdvisorRecommendation] = []
    attempts = 0
    max_attempts = max(proposal_count * 20, 50)
    while len(recommendations) < proposal_count and attempts < max_attempts:
        attempts += 1
        trial_info = smac.ask()
        sampled = {parameter.path: trial_info.config[parameter.path] for parameter in search_space.parameters}
        candidate = candidate_from_parameter_values(
            search_space,
            sampled,
            candidate_name=f"{search_space.candidate_prefix}_smac3_{len(recommendations) + 1}",
        )
        signature = _parameter_signature(search_space, candidate)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        recommendations.append(
            AdvisorRecommendation(
                rank=len(recommendations) + 1,
                candidate=candidate,
                rationale="SMAC3 recommendation from current condition history.",
            )
        )
    if len(recommendations) < proposal_count:
        _append_fallback_recommendations(
            search_space,
            recommendations,
            seen_signatures,
            proposal_count,
            seed,
            advisor_name="smac3",
        )

    return AdvisorSnapshot(
        advisor_name="smac3",
        search_space_id=search_space.search_space_id,
        history_run_ids=tuple(row.run_id for row in history_rows),
        recommendations=tuple(recommendations),
    )


ADVISOR_FACTORIES: dict[str, AdvisorFactory] = {
    "optuna_tpe": recommend_with_optuna,
    "smac3": recommend_with_smac3,
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        converted = value.tolist()
        if converted is not value:
            return _json_safe(converted)
    if hasattr(value, "item"):
        try:
            converted = value.item()
        except (TypeError, ValueError):
            return value
        if converted is not value:
            return _json_safe(converted)
    return value


def write_snapshot(snapshot: AdvisorSnapshot, path: Path) -> None:
    payload = {
        "advisor": snapshot.advisor_name,
        "search_space_id": snapshot.search_space_id,
        "history_run_ids": list(snapshot.history_run_ids),
        "recommendations": [
            {
                "rank": recommendation.rank,
                "rationale": recommendation.rationale,
                "candidate": {
                    "name": recommendation.candidate.name,
                    "model_family": recommendation.candidate.model_family,
                    "preprocessing": recommendation.candidate.preprocessing,
                    "resampling": recommendation.candidate.resampling,
                    "model": recommendation.candidate.model,
                },
            }
            for recommendation in snapshot.recommendations
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
