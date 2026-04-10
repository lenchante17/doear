from __future__ import annotations

import unittest

from autoresearch.sequence_runner import PreprocRoundSpec, build_preproc_submission_text


class PreprocSequenceRunnerTests(unittest.TestCase):
    def test_build_preproc_submission_text_keeps_model_fixed(self) -> None:
        spec = PreprocRoundSpec(
            name="round01_preproc_standard",
            analysis="Round 1 baseline.",
            preprocessing={"normalization": "standard", "outlier_strategy": "none"},
        )

        text = build_preproc_submission_text(
            benchmark="fashion_mnist_real",
            backend="sklearn",
            fixed_model={
                "hidden_dims": [64, 32],
                "activation": "relu",
                "normalization_layer": "none",
                "weight_decay": 0.0005,
                "learning_rate_init": 0.001,
                "batch_size": 64,
            },
            round_spec=spec,
        )

        self.assertIn('benchmark = "fashion_mnist_real"', text)
        self.assertIn('backend = "sklearn"', text)
        self.assertIn('model_family = "mlp"', text)
        self.assertIn('[candidates.preprocessing]', text)
        self.assertIn('normalization = "standard"', text)
        self.assertNotIn('notes =', text)
        self.assertIn('[candidates.model]', text)
        self.assertIn('activation = "relu"', text)
        self.assertIn('batch_size = 64', text)
        self.assertNotIn('[candidates.resampling]', text)


if __name__ == "__main__":
    unittest.main()
