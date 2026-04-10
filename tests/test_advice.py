from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from autoresearch.catalog import load_catalog
from autoresearch.domain import CandidateConfig
from autoresearch.runner import ExperimentRunner
from autoresearch.search_space import load_search_space


CATALOG_TEXT = """
[datasets.fashion_mnist]
kind = "npz_classification"
path = "data/fashion_mnist/fashion_mnist.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Local Fashion-MNIST npz benchmark."

[benchmarks.fashion_mnist_default]
dataset = "fashion_mnist"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["mlp"]
"""


SEARCH_SPACE_TEXT = """
id = "mlp_basic_v1"
benchmark = "fashion_mnist_default"
backend = "stub"
model_family = "mlp"
candidate_prefix = "mlp"

[defaults.preprocessing]
normalization = "none"
outlier_strategy = "none"

[defaults.resampling]
strategy = "none"

[defaults.model]
hidden_dims = [64, 32]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64

[[parameters]]
path = "preprocessing.normalization"
type = "categorical"
choices = ["none", "standard"]

[[parameters]]
path = "model.weight_decay"
type = "float"
low = 0.0001
high = 0.01
log = true
"""


ONE_CANDIDATE_CATALOG_TEXT = """
[datasets.fashion_mnist]
kind = "npz_classification"
path = "data/fashion_mnist/fashion_mnist.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Local Fashion-MNIST npz benchmark."

[benchmarks.fashion_mnist_default]
dataset = "fashion_mnist"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 1
allowed_model_families = ["mlp"]
"""


class AdviceWorkflowTests(unittest.TestCase):
    def write_text(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents.strip() + "\n", encoding="utf-8")

    def test_direct_advice_writes_submission_and_run_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "optuna_direct"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(root / "experiments" / "search_spaces" / "mlp_basic_v1.toml", SEARCH_SPACE_TEXT)
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "direct"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_basic_v1.toml"
""",
            )

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            from autoresearch.advisors import ADVISOR_FACTORIES, AdvisorRecommendation, AdvisorSnapshot

            def fake_optuna(search_space, history_rows, proposal_count, seed):
                self.assertEqual(search_space.search_space_id, "mlp_basic_v1")
                self.assertEqual(proposal_count, 2)
                return AdvisorSnapshot(
                    advisor_name="optuna_tpe",
                    search_space_id=search_space.search_space_id,
                    history_run_ids=tuple(row.run_id for row in history_rows),
                    recommendations=(
                        AdvisorRecommendation(
                            rank=1,
                            candidate=CandidateConfig(
                                name="optuna_rank1",
                                model_family="mlp",
                                preprocessing={"normalization": "standard", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [64, 32],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": 0.0003,
                                    "learning_rate_init": 0.001,
                                    "batch_size": 64,
                                },
                            ),
                            rationale="Top surrogate suggestion.",
                        ),
                        AdvisorRecommendation(
                            rank=2,
                            candidate=CandidateConfig(
                                name="optuna_rank2",
                                model_family="mlp",
                                preprocessing={"normalization": "none", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [128, 64],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": 0.0008,
                                    "learning_rate_init": 0.0007,
                                    "batch_size": 64,
                                },
                            ),
                            rationale="Nearby fallback suggestion.",
                        ),
                    ),
                )

            with patch.dict(ADVISOR_FACTORIES, {"optuna_tpe": fake_optuna}, clear=False):
                session = runner.advise_agent(agent_dir)
                self.assertEqual(session.policy_mode, "direct")
                self.assertTrue(session.wrote_submission)
                self.assertEqual(len(session.snapshot_paths), 1)
                submission_text = (agent_dir / "submission.toml").read_text(encoding="utf-8")
                self.assertIn('benchmark = "fashion_mnist_default"', submission_text)
                self.assertIn('backend = "stub"', submission_text)
                self.assertIn('name = "optuna_rank1"', submission_text)
                self.assertNotIn('name = "optuna_rank2"', submission_text)

                report = runner.run_agent_submission(agent_dir)

            artifact = json.loads(report.artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["agent_name"], "optuna_direct")
            self.assertEqual(artifact["policy_mode"], "direct")
            self.assertEqual(artifact["advisors"], ["optuna_tpe"])
            self.assertEqual(artifact["selection_origin"], "advisor_direct")
            self.assertEqual(len(artifact["advice_snapshot_paths"]), 1)

            history_text = (root / ".work" / "agents" / "optuna_direct" / "history.md").read_text(encoding="utf-8")
            self.assertIn("| mode |", history_text)
            self.assertIn("| advisors |", history_text)
            self.assertIn("advisor_direct", history_text)

    def test_direct_advice_serializes_numpy_scalars_in_recommendation_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "smac_direct"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(root / "experiments" / "search_spaces" / "mlp_basic_v1.toml", SEARCH_SPACE_TEXT)
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "direct"
advisors = ["smac3"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_basic_v1.toml"
""",
            )

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            from autoresearch.advisors import ADVISOR_FACTORIES, AdvisorRecommendation, AdvisorSnapshot

            def fake_smac(search_space, history_rows, proposal_count, seed):
                return AdvisorSnapshot(
                    advisor_name="smac3",
                    search_space_id=search_space.search_space_id,
                    history_run_ids=tuple(),
                    recommendations=(
                        AdvisorRecommendation(
                            rank=1,
                            candidate=CandidateConfig(
                                name="smac_rank1",
                                model_family="mlp",
                                preprocessing={"normalization": "standard", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [64, 32],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": np.float64(0.0004),
                                    "learning_rate_init": np.float64(0.0008),
                                    "batch_size": np.int64(64),
                                },
                            ),
                            rationale="SMAC3 top recommendation.",
                        ),
                        AdvisorRecommendation(
                            rank=2,
                            candidate=CandidateConfig(
                                name="smac_rank2",
                                model_family="mlp",
                                preprocessing={"normalization": "none", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [128, 64],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": np.float64(0.0008),
                                    "learning_rate_init": np.float64(0.0007),
                                    "batch_size": np.int64(128),
                                },
                            ),
                            rationale="SMAC3 fallback recommendation.",
                        ),
                    ),
                )

            with patch.dict(ADVISOR_FACTORIES, {"smac3": fake_smac}, clear=False):
                session = runner.advise_agent(agent_dir)

            self.assertTrue(session.wrote_submission)
            submission_text = (agent_dir / "submission.toml").read_text(encoding="utf-8")
            self.assertIn('name = "smac_rank1"', submission_text)
            self.assertNotIn('name = "smac_rank2"', submission_text)

    def test_direct_advice_uses_next_novel_candidate_when_top_choice_is_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "optuna_direct"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(root / "experiments" / "search_spaces" / "mlp_basic_v1.toml", SEARCH_SPACE_TEXT)
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "agent"
agent_profile = "01"
advisors = []
proposal_count = 2
""",
            )
            self.write_text(
                agent_dir / "submission.toml",
                """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "manual_anchor"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0003
learning_rate_init = 0.001
batch_size = 64
""",
            )

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)
            runner.run_agent_submission(agent_dir)
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "direct"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_basic_v1.toml"
""",
            )

            from autoresearch.advisors import ADVISOR_FACTORIES, AdvisorRecommendation, AdvisorSnapshot

            def fake_optuna(search_space, history_rows, proposal_count, seed):
                return AdvisorSnapshot(
                    advisor_name="optuna_tpe",
                    search_space_id=search_space.search_space_id,
                    history_run_ids=tuple(row.run_id for row in history_rows),
                    recommendations=(
                        AdvisorRecommendation(
                            rank=1,
                            candidate=CandidateConfig(
                                name="duplicate_rank1",
                                model_family="mlp",
                                preprocessing={"normalization": "standard", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [64, 32],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": 0.0003,
                                    "learning_rate_init": 0.001,
                                    "batch_size": 64,
                                },
                            ),
                            rationale="Exact duplicate of the previous run.",
                        ),
                        AdvisorRecommendation(
                            rank=2,
                            candidate=CandidateConfig(
                                name="novel_rank2",
                                model_family="mlp",
                                preprocessing={"normalization": "none", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [128, 64],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": 0.0008,
                                    "learning_rate_init": 0.0007,
                                    "batch_size": 64,
                                },
                            ),
                            rationale="Novel fallback suggestion.",
                        ),
                    ),
                )

            with patch.dict(ADVISOR_FACTORIES, {"optuna_tpe": fake_optuna}, clear=False):
                session = runner.advise_agent(agent_dir)

            self.assertTrue(session.wrote_submission)
            submission_text = (agent_dir / "submission.toml").read_text(encoding="utf-8")
            self.assertIn('name = "novel_rank2"', submission_text)
            self.assertNotIn('name = "duplicate_rank1"', submission_text)

    def test_agent_advice_writes_snapshots_but_keeps_submission_for_agent_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "agent_both"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(root / "experiments" / "search_spaces" / "mlp_basic_v1.toml", SEARCH_SPACE_TEXT)
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "agent"
advisors = ["optuna_tpe", "smac3"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_basic_v1.toml"
""",
            )
            self.write_text(
                agent_dir / "submission.toml",
                """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "manual_anchor"
model_family = "mlp"
[candidates.preprocessing]
normalization = "none"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
""",
            )

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            from autoresearch.advisors import ADVISOR_FACTORIES, AdvisorRecommendation, AdvisorSnapshot

            def fake_advisor(name, c_value):
                def _build(search_space, history_rows, proposal_count, seed):
                    return AdvisorSnapshot(
                        advisor_name=name,
                        search_space_id=search_space.search_space_id,
                        history_run_ids=tuple(),
                        recommendations=(
                            AdvisorRecommendation(
                                rank=1,
                                candidate=CandidateConfig(
                                    name=f"{name}_rank1",
                                    model_family="mlp",
                                    preprocessing={"normalization": "standard", "outlier_strategy": "none"},
                                    resampling={"strategy": "none"},
                                    model={
                                        "hidden_dims": [64, 32],
                                        "activation": "relu",
                                        "normalization_layer": "none",
                                        "weight_decay": c_value,
                                        "learning_rate_init": 0.001,
                                        "batch_size": 64,
                                    },
                                ),
                                rationale=f"{name} top recommendation.",
                            ),
                        ),
                    )
                return _build

            with patch.dict(
                ADVISOR_FACTORIES,
                {
                    "optuna_tpe": fake_advisor("optuna_tpe", 3.0),
                    "smac3": fake_advisor("smac3", 5.0),
                },
                clear=False,
            ):
                session = runner.advise_agent(agent_dir)
                self.assertEqual(session.policy_mode, "agent")
                self.assertFalse(session.wrote_submission)
                self.assertEqual(len(session.snapshot_paths), 2)
                summary_text = session.summary_path.read_text(encoding="utf-8")
                self.assertIn("optuna_tpe", summary_text)
                self.assertIn("smac3", summary_text)
                self.assertIn("manual_anchor", (agent_dir / "submission.toml").read_text(encoding="utf-8"))

                self.write_text(
                    agent_dir / "submission.toml",
                    """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "agent_choice"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [128, 64]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0004
learning_rate_init = 0.0008
batch_size = 64
""",
                )
                report = runner.run_agent_submission(agent_dir)

            artifact = json.loads(report.artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["policy_mode"], "agent")
            self.assertEqual(artifact["advisors"], ["optuna_tpe", "smac3"])
            self.assertEqual(artifact["selection_origin"], "agent_submission")
            self.assertEqual(len(artifact["advice_snapshot_paths"]), 2)

    def test_agent_advice_keeps_policy_proposal_count_when_submission_cap_is_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            agent_dir = root / "agents" / "agent_optuna"
            self.write_text(root / "experiments" / "benchmark_catalog.toml", ONE_CANDIDATE_CATALOG_TEXT)
            self.write_text(root / "experiments" / "search_spaces" / "mlp_basic_v1.toml", SEARCH_SPACE_TEXT)
            self.write_text(
                agent_dir / "policy.toml",
                """
mode = "agent"
agent_profile = "02"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_basic_v1.toml"
""",
            )
            self.write_text(agent_dir / "submission.toml", """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "manual_anchor"
model_family = "mlp"
[candidates.preprocessing]
normalization = "none"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
normalization_layer = "none"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
""")

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            from autoresearch.advisors import ADVISOR_FACTORIES, AdvisorRecommendation, AdvisorSnapshot

            def fake_optuna(search_space, history_rows, proposal_count, seed):
                self.assertEqual(proposal_count, 2)
                return AdvisorSnapshot(
                    advisor_name="optuna_tpe",
                    search_space_id=search_space.search_space_id,
                    history_run_ids=tuple(),
                    recommendations=(
                        AdvisorRecommendation(
                            rank=1,
                            candidate=CandidateConfig(
                                name="optuna_rank1",
                                model_family="mlp",
                                preprocessing={"normalization": "standard", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [64, 32],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": 0.0003,
                                    "learning_rate_init": 0.001,
                                    "batch_size": 64,
                                },
                            ),
                        ),
                        AdvisorRecommendation(
                            rank=2,
                            candidate=CandidateConfig(
                                name="optuna_rank2",
                                model_family="mlp",
                                preprocessing={"normalization": "none", "outlier_strategy": "none"},
                                resampling={"strategy": "none"},
                                model={
                                    "hidden_dims": [128, 64],
                                    "activation": "relu",
                                    "normalization_layer": "none",
                                    "weight_decay": 0.0009,
                                    "learning_rate_init": 0.0007,
                                    "batch_size": 64,
                                },
                            ),
                        ),
                    ),
                )

            with patch.dict(ADVISOR_FACTORIES, {"optuna_tpe": fake_optuna}, clear=False):
                session = runner.advise_agent(agent_dir)

            self.assertFalse(session.wrote_submission)
            payload = json.loads(session.snapshot_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(len(payload["recommendations"]), 2)

    def test_write_snapshot_serializes_numpy_scalar_model_values(self) -> None:
        from autoresearch.advisors import AdvisorRecommendation, AdvisorSnapshot, write_snapshot

        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot_path = Path(tmp_dir) / "snapshot.json"
            snapshot = AdvisorSnapshot(
                advisor_name="smac3",
                search_space_id="mlp_basic_v1",
                history_run_ids=("run_001",),
                recommendations=(
                    AdvisorRecommendation(
                        rank=1,
                        candidate=CandidateConfig(
                            name="smac_rank1",
                            model_family="mlp",
                            preprocessing={"normalization": "standard", "outlier_strategy": "none"},
                            resampling={"strategy": "none"},
                            model={
                                "hidden_dims": [64, 32],
                                "activation": "relu",
                                "normalization_layer": "none",
                                "weight_decay": np.float64(0.0004),
                                "learning_rate_init": np.float64(0.0008),
                                "batch_size": np.int64(64),
                            },
                        ),
                        rationale="SMAC3 top recommendation.",
                    ),
                ),
            )

            write_snapshot(snapshot, snapshot_path)

            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            candidate = payload["recommendations"][0]["candidate"]
            self.assertEqual(candidate["model"]["batch_size"], 64)
            self.assertAlmostEqual(candidate["model"]["weight_decay"], 0.0004)
            self.assertAlmostEqual(candidate["model"]["learning_rate_init"], 0.0008)

    def test_optuna_recommendation_skips_history_rows_outside_log_domain(self) -> None:
        from autoresearch.advisors import HistoryObservation, recommend_with_optuna

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            search_space_path = root / "experiments" / "search_spaces" / "mlp_basic_v1.toml"
            self.write_text(search_space_path, SEARCH_SPACE_TEXT)
            search_space = load_search_space(search_space_path)

            history_rows = [
                HistoryObservation(
                    run_id="run_001",
                    candidate=CandidateConfig(
                        name="bad_history",
                        model_family="mlp",
                        preprocessing={"normalization": "none", "outlier_strategy": "none"},
                        resampling={"strategy": "none"},
                        model={
                            "hidden_dims": [64, 32],
                            "activation": "relu",
                            "normalization_layer": "none",
                            "weight_decay": 0.0,
                            "learning_rate_init": 0.001,
                            "batch_size": 64,
                        },
                    ),
                    validation_score=0.25,
                )
            ]

            snapshot = recommend_with_optuna(
                search_space=search_space,
                history_rows=history_rows,
                proposal_count=2,
                seed=42,
            )

            self.assertEqual(snapshot.advisor_name, "optuna_tpe")
            self.assertEqual(len(snapshot.recommendations), 2)

    def test_smac_recommendation_skips_history_rows_outside_search_space(self) -> None:
        from autoresearch.advisors import HistoryObservation, recommend_with_smac3

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            search_space_path = root / "experiments" / "search_spaces" / "mlp_basic_v1.toml"
            self.write_text(search_space_path, SEARCH_SPACE_TEXT)
            search_space = load_search_space(search_space_path)

            history_rows = [
                HistoryObservation(
                    run_id="run_001",
                    candidate=CandidateConfig(
                        name="bad_history",
                        model_family="mlp",
                        preprocessing={"normalization": "maxabs", "outlier_strategy": "none"},
                        resampling={"strategy": "none"},
                        model={
                            "hidden_dims": [64, 32],
                            "activation": "relu",
                            "normalization_layer": "none",
                            "weight_decay": 0.0005,
                            "learning_rate_init": 0.001,
                            "batch_size": 64,
                        },
                    ),
                    validation_score=0.25,
                )
            ]

            snapshot = recommend_with_smac3(
                search_space=search_space,
                history_rows=history_rows,
                proposal_count=2,
                seed=42,
            )

            self.assertEqual(snapshot.advisor_name, "smac3")
            self.assertEqual(len(snapshot.recommendations), 2)


if __name__ == "__main__":
    unittest.main()
