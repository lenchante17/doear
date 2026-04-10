from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    kind: str
    task: str
    description: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark_id: str
    dataset_id: str
    metric: str
    backend: str
    random_seed: int
    validation_size: float
    test_size: float
    max_candidates_per_submission: int
    allowed_model_families: tuple[str, ...]
    description: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateConfig:
    name: str
    model_family: str
    preprocessing: dict[str, Any]
    resampling: dict[str, Any]
    model: dict[str, Any]


@dataclass(frozen=True)
class Submission:
    benchmark_id: str
    backend: str
    candidates: tuple[CandidateConfig, ...]
    source_path: Path


@dataclass(frozen=True)
class ValidatedSubmission:
    benchmark_id: str
    backend: str
    benchmark: BenchmarkSpec
    dataset: DatasetSpec
    candidates: tuple[CandidateConfig, ...]
    source_path: Path


@dataclass(frozen=True)
class CandidateResult:
    candidate_name: str
    model_family: str
    metric: str
    validation_score: float
    test_score: float
    rank: int
    backend_name: str
    summary: str
    preprocessing: dict[str, Any]
    resampling: dict[str, Any]
    model: dict[str, Any]
    benchmark_id: str = ""
    dataset_id: str = ""


@dataclass(frozen=True)
class RunReport:
    run_id: str
    agent_name: str
    benchmark_id: str
    dataset_id: str
    backend_name: str
    artifact_path: Path
    results: tuple[CandidateResult, ...]
    policy_mode: str = "agent"
    advisors: tuple[str, ...] = ()
    selection_origin: str = "manual_submission"
    advice_snapshot_paths: tuple[str, ...] = ()
    search_space_id: str = ""

    @property
    def best_result(self) -> CandidateResult:
        return self.results[0]


@dataclass(frozen=True)
class AdviceSession:
    agent_name: str
    policy_mode: str
    advisors: tuple[str, ...]
    snapshot_paths: tuple[Path, ...]
    summary_path: Path
    wrote_submission: bool
    search_space_id: str = ""
