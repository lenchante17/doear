from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from autoresearch.domain import RunReport
from autoresearch.runtime_paths import finalized_dir, runs_dir


PUBLIC_SCHEMA_VERSION = 4
FINAL_SCHEMA_VERSION = 4
SUPPORTED_PUBLIC_SCHEMA_VERSIONS = {3, 4}
SUPPORTED_FINAL_SCHEMA_VERSIONS = {3, 4}


def write_public_artifact(report: RunReport) -> None:
    payload = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "visibility": "validation_only",
        "selection_metric": "validation_score",
        "run_id": report.run_id,
        "agent_name": report.agent_name,
        "benchmark_id": report.benchmark_id,
        "dataset_id": report.dataset_id,
        "backend_name": report.backend_name,
        "policy_mode": report.policy_mode,
        "advisors": list(report.advisors),
        "selection_origin": report.selection_origin,
        "advice_snapshot_paths": list(report.advice_snapshot_paths),
        "search_space_id": report.search_space_id,
        "results": [
            {
                "candidate_name": result.candidate_name,
                "benchmark_id": result.benchmark_id or report.benchmark_id,
                "dataset_id": result.dataset_id or report.dataset_id,
                "model_family": result.model_family,
                "metric": result.metric,
                "validation_score": result.validation_score,
                "rank": result.rank,
                "backend_name": result.backend_name,
                "summary": result.summary,
                "preprocessing": result.preprocessing,
                "resampling": result.resampling,
                "model": result.model,
            }
            for result in report.results
        ],
        "best_result": {
            "candidate_name": report.best_result.candidate_name,
            "benchmark_id": report.best_result.benchmark_id or report.benchmark_id,
            "dataset_id": report.best_result.dataset_id or report.dataset_id,
            "model_family": report.best_result.model_family,
            "metric": report.best_result.metric,
            "validation_score": report.best_result.validation_score,
            "rank": report.best_result.rank,
            "backend_name": report.best_result.backend_name,
            "summary": report.best_result.summary,
            "preprocessing": report.best_result.preprocessing,
            "resampling": report.best_result.resampling,
            "model": report.best_result.model,
        },
    }
    report.artifact_path.parent.mkdir(parents=True, exist_ok=True)
    report.artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_finalized_artifact(report: RunReport) -> None:
    payload = {
        "schema_version": FINAL_SCHEMA_VERSION,
        "visibility": "finalized_with_test",
        "selection_metric": "validation_score",
        "run_id": report.run_id,
        "agent_name": report.agent_name,
        "benchmark_id": report.benchmark_id,
        "dataset_id": report.dataset_id,
        "backend_name": report.backend_name,
        "policy_mode": report.policy_mode,
        "advisors": list(report.advisors),
        "selection_origin": report.selection_origin,
        "advice_snapshot_paths": list(report.advice_snapshot_paths),
        "search_space_id": report.search_space_id,
        "results": [
            {
                "candidate_name": result.candidate_name,
                "benchmark_id": result.benchmark_id or report.benchmark_id,
                "dataset_id": result.dataset_id or report.dataset_id,
                "model_family": result.model_family,
                "metric": result.metric,
                "validation_score": result.validation_score,
                "test_score": result.test_score,
                "rank": result.rank,
                "backend_name": result.backend_name,
                "summary": result.summary,
                "preprocessing": result.preprocessing,
                "resampling": result.resampling,
                "model": result.model,
            }
            for result in report.results
        ],
        "best_result": {
            "candidate_name": report.best_result.candidate_name,
            "benchmark_id": report.best_result.benchmark_id or report.benchmark_id,
            "dataset_id": report.best_result.dataset_id or report.dataset_id,
            "model_family": report.best_result.model_family,
            "metric": report.best_result.metric,
            "validation_score": report.best_result.validation_score,
            "test_score": report.best_result.test_score,
            "rank": report.best_result.rank,
            "backend_name": report.best_result.backend_name,
            "summary": report.best_result.summary,
            "preprocessing": report.best_result.preprocessing,
            "resampling": report.best_result.resampling,
            "model": report.best_result.model,
        },
    }
    report.artifact_path.parent.mkdir(parents=True, exist_ok=True)
    report.artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
def load_public_artifacts(root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    for path in sorted(runs_dir(root).glob("*.json")) if runs_dir(root).exists() else []:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("schema_version") not in SUPPORTED_PUBLIC_SCHEMA_VERSIONS:
            continue
        if artifact.get("visibility") != "validation_only":
            continue
        results = artifact.get("results")
        if not isinstance(results, list) or not results:
            continue
        if "validation_score" not in results[0]:
            continue
        run_id = str(artifact.get("run_id", ""))
        if not run_id or run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        artifacts.append(artifact)
    return artifacts


def load_finalized_artifacts(root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    for path in sorted(finalized_dir(root).glob("*.json")) if finalized_dir(root).exists() else []:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("schema_version") not in SUPPORTED_FINAL_SCHEMA_VERSIONS:
            continue
        if artifact.get("visibility") != "finalized_with_test":
            continue
        results = artifact.get("results")
        if not isinstance(results, list) or not results:
            continue
        if "validation_score" not in results[0] or "test_score" not in results[0]:
            continue
        run_id = str(artifact.get("run_id", ""))
        if not run_id or run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        artifacts.append(artifact)
    return artifacts


def _validation_row_from_result(artifact: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    preprocessing = result.get("preprocessing", {})
    resampling = result.get("resampling", {})
    return {
        "run_id": artifact["run_id"],
        "agent": artifact["agent_name"],
        "benchmark": result.get("benchmark_id", artifact["benchmark_id"]),
        "dataset": result.get("dataset_id", artifact["dataset_id"]),
        "model": result["model_family"],
        "candidate": result["candidate_name"],
        "validation_score": float(result["validation_score"]),
        "backend": artifact["backend_name"],
        "config_summary": (
            f"norm={preprocessing.get('normalization', 'none')}, "
            f"outlier={preprocessing.get('outlier_strategy', 'none')}, "
            f"resample={resampling.get('strategy', 'none')}"
        ),
    }


def _final_row_from_result(artifact: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    row = _validation_row_from_result(artifact, result)
    row["test_score"] = float(result["test_score"])
    return row


def _flatten_validation_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        for result in artifact["results"]:
            rows.append(_validation_row_from_result(artifact, result))
    return rows


def _flatten_final_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        for result in artifact["results"]:
            rows.append(_final_row_from_result(artifact, result))
    return rows


def select_best_validation_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in _flatten_validation_rows(artifacts):
        key = (row["dataset"], row["model"], row["agent"])
        current = selected.get(key)
        if current is None or (
            row["validation_score"], row["run_id"]
        ) > (current["validation_score"], current["run_id"]):
            selected[key] = row
    return list(selected.values())


def select_best_final_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in _flatten_final_rows(artifacts):
        key = (row["dataset"], row["model"], row["agent"])
        current = selected.get(key)
        if current is None or (
            row["validation_score"], row["test_score"], row["run_id"]
        ) > (current["validation_score"], current["test_score"], current["run_id"]):
            selected[key] = row
    return list(selected.values())
