from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from autoresearch.catalog import load_catalog
from autoresearch.domain import CandidateConfig, Submission
from autoresearch.runner import ExperimentRunner
from autoresearch.submission import write_submission


CATALOG_TEXT = """
[datasets.toy]
kind = "npz_classification"
path = "data/toy.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Toy dataset for live advisory verification."

[benchmarks.toy_default]
dataset = "toy"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.2
test_size = 0.2
max_candidates_per_submission = 2
allowed_model_families = ["mlp"]
"""


SEARCH_SPACE_TEXT = """
id = "mlp_live_v1"
benchmark = "toy_default"
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
choices = ["none", "standard", "maxabs"]

[[parameters]]
path = "model.weight_decay"
type = "float"
low = 0.0001
high = 0.01
log = true
"""


BASELINE_SUBMISSION = Submission(
    benchmark_id="toy_default",
    backend="stub",
    candidates=(
        CandidateConfig(
            name="baseline_mlp",
            model_family="mlp",
            preprocessing={"normalization": "none", "outlier_strategy": "none"},
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
    ),
    source_path=Path("submission.toml"),
)


def _has_live_advisors() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("optuna", "smac", "ConfigSpace"))


@unittest.skipUnless(_has_live_advisors(), "optuna/smac/ConfigSpace are required for live advisory verification")
class LiveAdvisoryConditionTests(unittest.TestCase):
    def write_text(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents.strip() + "\n", encoding="utf-8")

    def _write_policy(self, agent_dir: Path, policy_text: str) -> None:
        self.write_text(agent_dir / "policy.toml", policy_text)
        write_submission(agent_dir / "submission.toml", BASELINE_SUBMISSION)

    def _submission_from_snapshots(self, paths: tuple[Path, ...], limit: int) -> Submission:
        candidates: list[CandidateConfig] = []
        seen: set[str] = set()
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for recommendation in payload["recommendations"]:
                candidate_payload = recommendation["candidate"]
                signature = json.dumps(candidate_payload, sort_keys=True)
                if signature in seen:
                    continue
                seen.add(signature)
                candidates.append(
                    CandidateConfig(
                        name=str(candidate_payload["name"]),
                        model_family=str(candidate_payload["model_family"]),
                        preprocessing=dict(candidate_payload.get("preprocessing", {})),
                        resampling=dict(candidate_payload.get("resampling", {})),
                        model=dict(candidate_payload.get("model", {})),
                    )
                )
                if len(candidates) >= limit:
                    return Submission(
                        benchmark_id="toy_default",
                        backend="stub",
                        candidates=tuple(candidates),
                        source_path=Path("submission.toml"),
                    )
        raise AssertionError("No candidates available from advisor snapshots.")

    def _plain_round_submission(self, round_index: int) -> Submission:
        candidates = (
            CandidateConfig(
                name=f"plain_round_{round_index}",
                model_family="mlp",
                preprocessing={
                    "normalization": ("none", "standard", "maxabs", "none", "standard")[round_index - 1],
                    "outlier_strategy": "none",
                },
                resampling={"strategy": "none"},
                model={
                    "hidden_dims": ([64, 32], [128, 64], [64, 64], [128, 128], [128, 64])[round_index - 1],
                    "activation": "relu",
                    "normalization_layer": "none",
                    "weight_decay": (0.0002, 0.0005, 0.001, 0.002, 0.0003)[round_index - 1],
                    "learning_rate_init": (0.001, 0.0007, 0.0005, 0.0003, 0.0015)[round_index - 1],
                    "batch_size": (32, 64, 64, 128, 32)[round_index - 1],
                },
            ),
        )
        return Submission(
            benchmark_id="toy_default",
            backend="stub",
            candidates=candidates,
            source_path=Path("submission.toml"),
        )

    def test_all_planned_setups_complete_five_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self.write_text(root / "experiments" / "benchmark_catalog.toml", CATALOG_TEXT)
            self.write_text(root / "experiments" / "search_spaces" / "mlp_live_v1.toml", SEARCH_SPACE_TEXT)

            policies = {
                "optuna_direct": """
mode = "direct"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_live_v1.toml"
""",
                "smac3_direct": """
mode = "direct"
advisors = ["smac3"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_live_v1.toml"
""",
                "agent_plain": """
mode = "agent"
agent_profile = "01"
advisors = []
proposal_count = 2
""",
                "agent_optuna": """
mode = "agent"
agent_profile = "02"
advisors = ["optuna_tpe"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_live_v1.toml"
""",
                "agent_smac3": """
mode = "agent"
agent_profile = "03"
advisors = ["smac3"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_live_v1.toml"
""",
                "agent_optuna_smac3": """
mode = "agent"
agent_profile = "01"
advisors = ["optuna_tpe", "smac3"]
proposal_count = 2
search_space = "experiments/search_spaces/mlp_live_v1.toml"
""",
            }
            for name, policy_text in policies.items():
                self._write_policy(root / "agents" / name, policy_text)

            catalog = load_catalog(root / "experiments" / "benchmark_catalog.toml")
            runner = ExperimentRunner(root=root, catalog=catalog)

            verification_rows: list[tuple[str, str, str, int, int]] = []

            for name in (
                "optuna_direct",
                "smac3_direct",
                "agent_plain",
                "agent_optuna",
                "agent_smac3",
                "agent_optuna_smac3",
            ):
                agent_dir = root / "agents" / name
                run_ids: list[str] = []

                for round_index in range(1, 6):
                    if name == "agent_plain":
                        write_submission(agent_dir / "submission.toml", self._plain_round_submission(round_index))
                    else:
                        session = runner.advise_agent(agent_dir)
                        if name.endswith("direct"):
                            self.assertTrue(session.wrote_submission)
                        else:
                            self.assertFalse(session.wrote_submission)
                            submission = self._submission_from_snapshots(session.snapshot_paths, limit=1)
                            write_submission(agent_dir / "submission.toml", submission)

                    report = runner.run_agent_submission(agent_dir)
                    run_ids.append(report.run_id)

                self.assertEqual(len(set(run_ids)), 5)
                artifact = json.loads(report.artifact_path.read_text(encoding="utf-8"))
                history_text = (root / ".work" / "agents" / name / "history.md").read_text(encoding="utf-8")

                if name == "agent_plain":
                    self.assertEqual(artifact["selection_origin"], "manual_submission")
                    self.assertEqual(artifact["advisors"], [])
                elif name.endswith("direct"):
                    self.assertEqual(artifact["selection_origin"], "advisor_direct")
                else:
                    self.assertEqual(artifact["selection_origin"], "agent_submission")

                self.assertIn("| mode |", history_text)
                self.assertEqual(artifact["policy_mode"], "direct" if name.endswith("direct") else "agent")
                if name == "agent_plain":
                    self.assertIn("tight keep-or-discard mutation around that incumbent", (agent_dir / "program.md").read_text(encoding="utf-8"))
                if name == "agent_optuna":
                    self.assertIn("choosing the next screening contrast", (agent_dir / "program.md").read_text(encoding="utf-8"))
                if name == "agent_smac3":
                    self.assertIn("Stage:", (agent_dir / "program.md").read_text(encoding="utf-8"))
                verification_rows.append(
                    (
                        name,
                        artifact["policy_mode"],
                        artifact["selection_origin"],
                        len(artifact["results"]),
                        len(run_ids),
                    )
                )

            self.assertEqual(len(verification_rows), 6)
            self.assertEqual(
                {row[0] for row in verification_rows},
                {
                    "optuna_direct",
                    "smac3_direct",
                    "agent_plain",
                    "agent_optuna",
                    "agent_smac3",
                    "agent_optuna_smac3",
                },
            )


if __name__ == "__main__":
    unittest.main()
