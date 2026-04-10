from __future__ import annotations

import unittest
from pathlib import Path

from autoresearch.backends import SklearnBackend
from autoresearch.catalog import load_catalog
from autoresearch.domain import CandidateConfig
from autoresearch.repo_mlp import RepoMLPClassifier


class BackendRoutingTests(unittest.TestCase):
    def test_gelu_mlp_uses_repo_native_classifier(self) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
        benchmark = catalog.benchmark("twenty_newsgroups_real")

        backend = SklearnBackend(root)
        estimator = backend._make_estimator(
            backend._require_sklearn(),
            CandidateConfig(
                name="gelu_candidate",
                model_family="mlp",
                preprocessing={"normalization": "maxabs", "outlier_strategy": "none"},
                resampling={"strategy": "none"},
                model={
                    "hidden_dims": [128, 64],
                    "activation": "gelu",
                    "normalization_layer": "none",
                    "weight_decay": 0.0002357985477,
                    "learning_rate_init": 0.0009962395436,
                    "batch_size": 32,
                },
            ),
            benchmark.random_seed,
        )

        self.assertIsInstance(estimator, RepoMLPClassifier)


if __name__ == "__main__":
    unittest.main()
