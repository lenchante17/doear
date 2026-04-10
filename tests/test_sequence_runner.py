from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from autoresearch.sequence_runner import (
    PreprocRoundSpec,
    RoundSpec,
    run_round_sequence,
    build_preproc_submission_text,
    build_submission_text,
)


class SequenceRunnerTests(unittest.TestCase):
    def test_build_submission_text_keeps_preprocessing_and_resampling_implicit(self) -> None:
        spec = RoundSpec(
            name="round01_mlp_small",
            analysis="Round 1 baseline.",
            model={
                "hidden_dims": [64, 32],
                "activation": "relu",
                "normalization_layer": "none",
                "weight_decay": 0.0005,
                "learning_rate_init": 0.001,
                "batch_size": 64,
            },
        )

        text = build_submission_text(
            benchmark="cifar10_real",
            backend="sklearn",
            round_spec=spec,
        )

        self.assertIn('benchmark = "cifar10_real"', text)
        self.assertIn('backend = "sklearn"', text)
        self.assertIn('model_family = "mlp"', text)
        self.assertIn('activation = "relu"', text)
        self.assertIn("batch_size = 64", text)
        self.assertNotIn("notes =", text)
        self.assertNotIn("[candidates.preprocessing]", text)
        self.assertNotIn("[candidates.resampling]", text)

    def test_build_preproc_submission_text_omits_model_block_when_using_defaults(self) -> None:
        spec = PreprocRoundSpec(
            name="round01_minmax",
            analysis="Round 1: min-max scaling only.",
            preprocessing={"normalization": "minmax", "outlier_strategy": "none"},
        )

        text = build_preproc_submission_text(
            benchmark="fashion_mnist_real",
            backend="sklearn",
            fixed_model={},
            round_spec=spec,
        )

        self.assertIn('benchmark = "fashion_mnist_real"', text)
        self.assertIn('backend = "sklearn"', text)
        self.assertIn("[candidates.preprocessing]", text)
        self.assertIn('normalization = "minmax"', text)
        self.assertNotIn("notes =", text)
        self.assertNotIn("[candidates.model]", text)

    def test_run_round_sequence_relocks_submission_to_final_winner(self) -> None:
        rounds = [
            PreprocRoundSpec(
                name="round01_none",
                analysis="Round 1.",
                preprocessing={"normalization": "none", "outlier_strategy": "none"},
            ),
            PreprocRoundSpec(
                name="round02_standard",
                analysis="Round 2.",
                preprocessing={"normalization": "standard", "outlier_strategy": "none"},
            ),
        ]
        write_calls: list[str] = []

        class DummyRunner:
            def __init__(self, root: Path, catalog: object) -> None:
                pass

            def run_agent_submission(self, agent_dir: Path):
                candidate_name = write_calls[-1]
                score = 0.8 if candidate_name == "round01_none" else 0.9

                class Report:
                    run_id = f"run-{candidate_name}"

                    class BestResult:
                        validation_score = score

                    best_result = BestResult()

                return Report()

            def finalize_agent(self, agent_dir: Path):
                class Report:
                    class BestResult:
                        candidate_name = "round02_standard"

                    best_result = BestResult()

                return Report()

        def fake_writer(agent_dir: Path, benchmark: str, backend: str, round_spec: PreprocRoundSpec) -> None:
            write_calls.append(round_spec.name)

        with patch("autoresearch.sequence_runner.load_catalog", return_value=object()), patch(
            "autoresearch.sequence_runner.ExperimentRunner",
            DummyRunner,
        ), patch(
            "autoresearch.sequence_runner.append_report_entry",
            return_value=None,
        ):
            run_round_sequence(
                root=Path("/tmp/fake-root"),
                agent_dir=Path("/tmp/fake-agent"),
                benchmark="fashion_mnist_real",
                backend="sklearn",
                rounds=rounds,  # type: ignore[arg-type]
                submission_writer=fake_writer,
            )

        self.assertEqual(write_calls, ["round01_none", "round02_standard", "round02_standard"])


if __name__ == "__main__":
    unittest.main()
