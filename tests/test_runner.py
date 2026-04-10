from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from autoresearch.catalog import load_catalog
from autoresearch.cli import build_parser
from autoresearch.runner import ExperimentRunner
from autoresearch.validation import SubmissionValidationError


CATALOG_TEXT = """
[datasets.fashion_mnist]
kind = "npz_classification"
path = "data/fashion_mnist/fashion_mnist.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Local Fashion-MNIST npz benchmark."

[datasets.cifar10]
kind = "npz_classification"
path = "data/cifar10/cifar10.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Local CIFAR-10 npz benchmark."

[benchmarks.fashion_mnist_default]
dataset = "fashion_mnist"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["tree", "svm", "mlp"]

[benchmarks.cifar10_default]
dataset = "cifar10"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["svm", "mlp"]
"""


SINGLE_CANDIDATE_SUBMISSION = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "svm_balanced"
model_family = "svm"

[candidates.preprocessing]
normalization = "standard"
outlier_strategy = "clip_iqr"
outlier_iqr_multiplier = 1.5

[candidates.resampling]
strategy = "oversample_minority"
target_ratio = 1.0

[candidates.model]
c = 1.0
kernel = "rbf"
gamma = "scale"
class_weight = "balanced"
"""

MULTI_CANDIDATE_SUBMISSION = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "svm_balanced"
model_family = "svm"

[candidates.preprocessing]
normalization = "standard"
outlier_strategy = "clip_iqr"
outlier_iqr_multiplier = 1.5

[candidates.resampling]
strategy = "oversample_minority"
target_ratio = 1.0

[candidates.model]
c = 1.0
kernel = "rbf"
gamma = "scale"
class_weight = "balanced"

[[candidates]]
name = "tree_weighted"
model_family = "tree"

[candidates.preprocessing]
normalization = "none"
outlier_strategy = "none"

[candidates.resampling]
strategy = "undersample_majority"
target_ratio = 1.0

[candidates.model]
criterion = "gini"
max_depth = 6
min_samples_leaf = 2
class_weight = "balanced"
"""


class ExperimentRunnerTests(unittest.TestCase):
    def write_text(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents.strip() + "\n", encoding="utf-8")

    def test_run_exposes_validation_only_until_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(
                root / "agents" / "steady_refiner" / "submission.toml",
                SINGLE_CANDIDATE_SUBMISSION,
            )

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            report = runner.run_agent_submission(root / "agents" / "steady_refiner")

            self.assertEqual(report.agent_name, "steady_refiner")
            self.assertEqual(report.benchmark_id, "fashion_mnist_default")
            self.assertEqual(len(report.results), 1)
            self.assertTrue(report.artifact_path.exists())
            self.assertEqual(report.artifact_path.parent, root / ".work" / "runs")

            import json

            artifact = json.loads(report.artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["agent_name"], "steady_refiner")
            self.assertEqual(artifact["best_result"]["candidate_name"], report.best_result.candidate_name)
            self.assertIn("validation_score", artifact["results"][0])
            self.assertNotIn("test_score", artifact["results"][0])
            self.assertNotIn("notes", artifact)

            history_text = (root / ".work" / "agents" / "steady_refiner" / "history.md").read_text(encoding="utf-8")
            self.assertIn("| run_id | benchmark | dataset | candidate | model |", history_text)
            self.assertIn("| validation_score |", history_text)
            self.assertIn("| run_best_candidate |", history_text)
            self.assertIn("| agent_best_candidate |", history_text)
            self.assertIn("| dataset_model_best_candidate |", history_text)
            self.assertNotIn("| review |", history_text)
            self.assertNotIn("test_score", history_text)
            self.assertIn("svm_balanced", history_text)
            self.assertIn("steady_refiner", history_text)
            self.assertFalse((root / "agents" / "steady_refiner" / "history.md").exists())
            self.assertFalse((root / "agents" / "steady_refiner" / "feedback.md").exists())
            report_text = (root / ".work" / "agents" / "steady_refiner" / "report.md").read_text(encoding="utf-8")
            self.assertIn("# Report", report_text)

            leaderboard_text = (root / ".work" / "leaderboard.md").read_text(encoding="utf-8")
            self.assertIn("## Validation Set Results", leaderboard_text)
            self.assertIn("## Test Set Results", leaderboard_text)
            self.assertIn("| dataset | model | agent | candidate |", leaderboard_text)
            self.assertIn("steady_refiner", leaderboard_text)
            self.assertIn("fashion_mnist", leaderboard_text)
            self.assertIn("svm", leaderboard_text)
            self.assertIn("No finalized agents yet.", leaderboard_text)
            self.assertNotIn("test_score", leaderboard_text.lower())

            final_report = runner.finalize_agent(root / "agents" / "steady_refiner")
            self.assertEqual(final_report.agent_name, "steady_refiner")
            self.assertTrue(final_report.artifact_path.exists())
            self.assertEqual(len(final_report.results), 1)

            finalized_feedback_text = (
                root / ".work" / "agents" / "steady_refiner" / "final_report.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Test Score", finalized_feedback_text)
            self.assertIn("svm", finalized_feedback_text)

            finalized_leaderboard_text = (root / ".work" / "leaderboard.md").read_text(encoding="utf-8")
            self.assertIn("## Validation Set Results", finalized_leaderboard_text)
            self.assertIn("## Test Set Results", finalized_leaderboard_text)
            self.assertIn("| dataset | model | agent | candidate | benchmark | validation_score | test_score |", finalized_leaderboard_text)
            self.assertNotIn("No finalized agents yet.", finalized_leaderboard_text)

    def test_run_rejects_multiple_candidates_per_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(
                root / "agents" / "steady_refiner" / "submission.toml",
                MULTI_CANDIDATE_SUBMISSION,
            )

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            with self.assertRaises(SubmissionValidationError) as ctx:
                runner.run_agent_submission(root / "agents" / "steady_refiner")

            self.assertIn("Exactly one candidate", str(ctx.exception))

    def test_run_rejects_duplicate_config_for_same_agent_and_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "steady_refiner"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(agent_dir / "submission.toml", SINGLE_CANDIDATE_SUBMISSION)

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            runner.run_agent_submission(agent_dir)

            with self.assertRaises(SubmissionValidationError) as ctx:
                runner.run_agent_submission(agent_dir)

            self.assertIn("previously evaluated config", str(ctx.exception))

    def test_finalize_agent_preserves_result_scope_across_multiple_benchmarks(self) -> None:
        catalog_text = """
[datasets.ds1]
kind = "npz_classification"
path = "data/ds1.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "First toy dataset."

[datasets.ds2]
kind = "npz_classification"
path = "data/ds2.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Second toy dataset."

[benchmarks.bench_one]
dataset = "ds1"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.2
test_size = 0.2
max_candidates_per_submission = 1
allowed_model_families = ["svm"]

[benchmarks.bench_two]
dataset = "ds2"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.2
test_size = 0.2
max_candidates_per_submission = 1
allowed_model_families = ["svm"]
"""
        submission_one = """
benchmark = "bench_one"
backend = "stub"

[[candidates]]
name = "c1"
model_family = "svm"

[candidates.model]
c = 1.0
"""
        submission_two = """
benchmark = "bench_two"
backend = "stub"

[[candidates]]
name = "c2"
model_family = "svm"

[candidates.model]
c = 2.0
"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "multi_agent"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", catalog_text)

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            self.write_text(agent_dir / "submission.toml", submission_one)
            runner.run_agent_submission(agent_dir)
            self.write_text(agent_dir / "submission.toml", submission_two)
            runner.run_agent_submission(agent_dir)

            final_report = runner.finalize_agent(agent_dir)

            self.assertEqual(final_report.benchmark_id, "multiple")
            self.assertEqual(final_report.dataset_id, "multiple")
            self.assertEqual(
                {(result.benchmark_id, result.dataset_id, result.candidate_name) for result in final_report.results},
                {
                    ("bench_one", "ds1", "c1"),
                    ("bench_two", "ds2", "c2"),
                },
            )

            artifact = json.loads(final_report.artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["benchmark_id"], "multiple")
            self.assertEqual(artifact["dataset_id"], "multiple")
            self.assertEqual(
                {
                    (row["benchmark_id"], row["dataset_id"], row["candidate_name"])
                    for row in artifact["results"]
                },
                {
                    ("bench_one", "ds1", "c1"),
                    ("bench_two", "ds2", "c2"),
                },
            )

            final_report_text = (root / ".work" / "agents" / "multi_agent" / "final_report.md").read_text(encoding="utf-8")
            self.assertIn("across multiple benchmarks", final_report_text)
            self.assertIn("| bench_one | ds1 | svm | c1 |", final_report_text)
            self.assertIn("| bench_two | ds2 | svm | c2 |", final_report_text)


class CliDependencyBoundaryTests(unittest.TestCase):
    def write_text(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents.strip() + "\n", encoding="utf-8")

    def test_list_benchmarks_path_does_not_require_numpy(self) -> None:
        catalog_text = """
[datasets.toy]
kind = "npz_classification"
path = "data/toy.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Toy dataset."

[benchmarks.toy_stub]
dataset = "toy"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.2
test_size = 0.2
max_candidates_per_submission = 1
allowed_model_families = ["svm"]
"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog_path = root / "benchmark_catalog.toml"
            self.write_text(catalog_path, catalog_text)

            script = f"""
import contextlib
import importlib.abc
import io
import sys

class BlockRepoMLP(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {{"numpy", "autoresearch.repo_mlp"}}:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockRepoMLP())
from autoresearch.cli import main

stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    exit_code = main(["list-benchmarks", "--catalog", {str(catalog_path)!r}])

print(exit_code)
print(stdout.getvalue(), end="")
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("0\n", result.stdout)
            self.assertIn("toy_stub", result.stdout)


class CliSurfaceTests(unittest.TestCase):
    def test_parser_does_not_expose_run_agent_loop(self) -> None:
        parser = build_parser()
        choices = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]

        self.assertNotIn("run-agent-loop", choices)

    def test_parser_does_not_expose_auto_run(self) -> None:
        parser = build_parser()
        choices = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]

        self.assertNotIn("auto-run", choices)

    def test_isolated_setup_readmes_do_not_advertise_auto_run(self) -> None:
        from scripts import setup_isolated_cifar_mlp_experiments as cifar_setup
        from scripts import setup_isolated_mlp_benchmark_experiments as mlp_setup

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            mlp_setup._write_experiment_readme(
                root / "mlp",
                mlp_setup.EXPERIMENT_SPECS[0],
                "fashion_mnist_real",
            )
            cifar_setup._write_experiment_readme(
                root / "cifar",
                cifar_setup.EXPERIMENT_SPECS[0],
            )

            mlp_readme = (root / "mlp" / "EXPERIMENT.md").read_text(encoding="utf-8")
            cifar_readme = (root / "cifar" / "EXPERIMENT.md").read_text(encoding="utf-8")

            self.assertNotIn("Auto run:", mlp_readme)
            self.assertNotIn("Auto run:", cifar_readme)


if __name__ == "__main__":
    unittest.main()
