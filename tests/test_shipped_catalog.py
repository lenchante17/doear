from __future__ import annotations

import unittest
from pathlib import Path

from autoresearch.backends import StubBackend
from autoresearch.catalog import load_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "experiments" / "benchmark_catalog.toml"
EXPECTED_DATASET_IDS = {"cifar10", "fashion_mnist", "twenty_newsgroups", "sms_spam"}
EXPECTED_BENCHMARK_IDS = {
    "cifar10_real",
    "fashion_mnist_real",
    "twenty_newsgroups_real",
    "sms_spam_real",
}


class ShippedCatalogTests(unittest.TestCase):
    def test_shipped_catalog_excludes_obsolete_datasets_and_benchmarks(self) -> None:
        catalog = load_catalog(CATALOG_PATH)

        self.assertEqual(set(catalog.datasets), EXPECTED_DATASET_IDS)
        self.assertEqual(set(catalog.benchmarks), EXPECTED_BENCHMARK_IDS)

    def test_shipped_real_benchmarks_are_mlp_only(self) -> None:
        catalog = load_catalog(CATALOG_PATH)

        for benchmark_id in EXPECTED_BENCHMARK_IDS:
            self.assertEqual(catalog.benchmark(benchmark_id).allowed_model_families, ("mlp",))

    def test_stub_backend_excludes_obsolete_dataset_priors(self) -> None:
        shipped_dataset_ids = {
            dataset_id for dataset_id, _family in StubBackend.FAMILY_PRIORS
        }
        shipped_ideal_ids = {
            dataset_id for dataset_id, _family in StubBackend.IDEALS
        }

        self.assertEqual(shipped_dataset_ids, EXPECTED_DATASET_IDS)
        self.assertEqual(shipped_ideal_ids, EXPECTED_DATASET_IDS)


if __name__ == "__main__":
    unittest.main()
