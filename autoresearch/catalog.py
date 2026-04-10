from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from autoresearch.domain import BenchmarkSpec, DatasetSpec


class CatalogLoadError(ValueError):
    pass


@dataclass(frozen=True)
class Catalog:
    path: Path
    datasets: dict[str, DatasetSpec]
    benchmarks: dict[str, BenchmarkSpec]

    def dataset(self, dataset_id: str) -> DatasetSpec:
        try:
            return self.datasets[dataset_id]
        except KeyError as exc:
            raise CatalogLoadError(f"Unknown dataset: {dataset_id}") from exc

    def benchmark(self, benchmark_id: str) -> BenchmarkSpec:
        try:
            return self.benchmarks[benchmark_id]
        except KeyError as exc:
            raise CatalogLoadError(f"Unknown benchmark: {benchmark_id}") from exc


def _split_known_fields(raw: dict[str, Any], keys: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    known = {key: raw[key] for key in keys if key in raw}
    extra = {key: value for key, value in raw.items() if key not in keys}
    return known, extra


def load_catalog(path: Path) -> Catalog:
    path = Path(path)
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    datasets_section = raw.get("datasets")
    benchmarks_section = raw.get("benchmarks")
    if not isinstance(datasets_section, dict) or not isinstance(benchmarks_section, dict):
        raise CatalogLoadError("Catalog must define [datasets.*] and [benchmarks.*] sections.")

    datasets: dict[str, DatasetSpec] = {}
    for dataset_id, dataset_raw in datasets_section.items():
        if not isinstance(dataset_raw, dict):
            raise CatalogLoadError(f"Dataset entry {dataset_id!r} must be a table.")
        known, extra = _split_known_fields(
            dataset_raw,
            {"kind", "task", "description"},
        )
        datasets[dataset_id] = DatasetSpec(
            dataset_id=dataset_id,
            kind=str(known.get("kind", "")),
            task=str(known.get("task", "classification")),
            description=str(known.get("description", "")),
            options=extra,
        )

    benchmarks: dict[str, BenchmarkSpec] = {}
    for benchmark_id, benchmark_raw in benchmarks_section.items():
        if not isinstance(benchmark_raw, dict):
            raise CatalogLoadError(f"Benchmark entry {benchmark_id!r} must be a table.")
        known, extra = _split_known_fields(
            benchmark_raw,
            {
                "dataset",
                "metric",
                "backend",
                "random_seed",
                "validation_size",
                "test_size",
                "max_candidates_per_submission",
                "allowed_model_families",
                "description",
            },
        )
        dataset_id = str(known.get("dataset", ""))
        if dataset_id not in datasets:
            raise CatalogLoadError(
                f"Benchmark {benchmark_id!r} references unknown dataset {dataset_id!r}."
            )
        allowed_families = known.get("allowed_model_families", ())
        if not isinstance(allowed_families, list):
            raise CatalogLoadError(
                f"Benchmark {benchmark_id!r} must define allowed_model_families as an array."
            )
        validation_size = float(known.get("validation_size", 0.2))
        test_size = float(known.get("test_size", 0.2))
        if validation_size <= 0.0 or test_size <= 0.0 or validation_size + test_size >= 1.0:
            raise CatalogLoadError(
                f"Benchmark {benchmark_id!r} must satisfy "
                "0 < validation_size, test_size and validation_size + test_size < 1."
            )
        benchmarks[benchmark_id] = BenchmarkSpec(
            benchmark_id=benchmark_id,
            dataset_id=dataset_id,
            metric=str(known.get("metric", "accuracy")),
            backend=str(known.get("backend", "stub")),
            random_seed=int(known.get("random_seed", 42)),
            validation_size=validation_size,
            test_size=test_size,
            max_candidates_per_submission=int(known.get("max_candidates_per_submission", 4)),
            allowed_model_families=tuple(str(item) for item in allowed_families),
            description=str(known.get("description", "")),
            options=extra,
        )

    shared_seeds = {benchmark.random_seed for benchmark in benchmarks.values()}
    if len(shared_seeds) > 1:
        raise CatalogLoadError(
            "All benchmarks must share one common random_seed so dataset splits stay aligned."
        )

    return Catalog(path=path, datasets=datasets, benchmarks=benchmarks)
