from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autoresearch.catalog import CatalogLoadError, load_catalog
from autoresearch.submission import SubmissionLoadError, load_submission
from autoresearch.validation import SubmissionValidationError, validate_submission


CATALOG_TEXT = """
[datasets.fashion_mnist]
kind = "npz_classification"
path = "data/fashion_mnist/fashion_mnist.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Fashion-MNIST npz benchmark."

[benchmarks.fashion_mnist_default]
dataset = "fashion_mnist"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["tree", "svm", "mlp"]
"""


VALID_SUBMISSION = """
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
strategy = "none"

[candidates.model]
criterion = "gini"
max_depth = 6
min_samples_leaf = 2
class_weight = "balanced"
"""


TOO_MANY_CANDIDATES = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "one"
model_family = "svm"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
c = 0.5
kernel = "rbf"

[[candidates]]
name = "two"
model_family = "svm"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
c = 1.0
kernel = "rbf"

[[candidates]]
name = "three"
model_family = "tree"
[candidates.preprocessing]
normalization = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
max_depth = 4

[[candidates]]
name = "four"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "oversample_minority"
target_ratio = 1.0
[candidates.model]
hidden_dim1 = 64
hidden_dim2 = 32
activation = "relu"
alpha = 0.0005
max_iter = 100
"""


UNKNOWN_FAMILY = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "cheat_code"
model_family = "xgboost"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
depth = 6
"""


MISMATCHED_SEEDS_CATALOG = """
[datasets.fashion_mnist]
kind = "npz_classification"
path = "data/fashion_mnist/fashion_mnist.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Fashion-MNIST npz benchmark."

[datasets.cifar10_extra]
kind = "npz_classification"
path = "data/cifar10/alternate_cifar10.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "Alternate CIFAR-10 npz benchmark."

[datasets.cifar10]
kind = "npz_classification"
path = "data/cifar10/cifar10.npz"
target_key = "y"
features_key = "x"
task = "classification"
description = "CIFAR-10 npz benchmark."

[benchmarks.fashion_mnist_default]
dataset = "fashion_mnist"
metric = "accuracy"
backend = "stub"
random_seed = 42
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["tree", "svm", "mlp"]

[benchmarks.cifar10_extra_default]
dataset = "cifar10_extra"
metric = "accuracy"
backend = "stub"
random_seed = 7
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["tree", "svm", "mlp"]

[benchmarks.cifar10_default]
dataset = "cifar10"
metric = "accuracy"
backend = "stub"
random_seed = 7
validation_size = 0.15
test_size = 0.15
max_candidates_per_submission = 2
allowed_model_families = ["tree", "svm", "mlp"]
"""


INVALID_PREPROCESSING = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "bad_scaler"
model_family = "svm"
[candidates.preprocessing]
normalization = "whiten"
[candidates.resampling]
strategy = "none"
[candidates.model]
c = 1.0
kernel = "rbf"
"""


INVALID_SVD_PROJECTION = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "bad_projection"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "none"
projection = "svd"
projection_dim = 32
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
solver = "adam"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
"""


VALID_EXPANDED_TREE_SVM = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "svm_extended"
model_family = "svm"
[candidates.preprocessing]
normalization = "mean_center"
outlier_strategy = "clip_percentile"
outlier_quantile_low = 0.02
outlier_quantile_high = 0.98
projection = "pca"
projection_dim = 32
[candidates.resampling]
strategy = "none"
[candidates.model]
c = 2.5
kernel = "sigmoid"
gamma = "auto"
coef0 = 0.3
tol = 0.0005
shrinking = false
class_weight = "balanced"

[[candidates]]
name = "tree_extended"
model_family = "tree"
[candidates.preprocessing]
normalization = "signed_log1p"
outlier_strategy = "none"
projection = "pca"
projection_dim = 24
projection_whiten = true
[candidates.resampling]
strategy = "none"
[candidates.model]
criterion = "log_loss"
max_depth = 8
max_features = 0.5
max_leaf_nodes = 32
min_impurity_decrease = 0.0001
ccp_alpha = 0.0002
"""


VALID_EXPANDED_MLP = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_expanded"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "clip_percentile"
outlier_quantile_low = 0.02
outlier_quantile_high = 0.98
projection = "pca"
projection_dim = 32
[candidates.resampling]
strategy = "oversample_minority"
target_ratio = 1.0
[candidates.model]
hidden_dims = [64, 32, 16]
activation = "leaky_relu"
activation_alpha = 0.1
weight_init = "he_uniform"
use_bias = false
input_noise_std = 0.03
hidden_noise_std = 0.07
solver = "adamw"
normalization_layer = "layernorm"
weight_decay = 0.0005
normalization_weight_decay = 0.0002
dropout_rate = 0.2
input_dropout_rate = 0.05
label_smoothing = 0.1
gradient_clip_norm = 1.5
learning_rate_init = 0.001
learning_rate = "cosine"
min_learning_rate = 0.00001
warmup_steps = 8
batch_size = 64
early_stopping = false
validation_fraction = 0.2
n_iter_no_change = 7
shuffle = true
loss = "focal"
focal_gamma = 1.5
"""


VALID_MLP_PROJECTION_SEARCH = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_projection_search"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "none"
projection = "pca"
projection_dim = 64
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
solver = "adam"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
"""


VALID_MLP_REPO_NATIVE_CONTROLS = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_overfree"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32, 16]
activation = "relu"
solver = "adam"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
dropout_rate = 0.2
"""


VALID_MLP_OUTLIER_SEARCH = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_outlier_search"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "clip_zscore"
outlier_zscore_threshold = 3.0
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
solver = "adam"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
"""


VALID_MLP_RESAMPLING_SEARCH = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_resampling_search"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "none"
[candidates.resampling]
strategy = "oversample_minority"
target_ratio = 1.0
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
solver = "adam"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
"""


VALID_EXOTIC_MLP_PROGRAM = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_exotic"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32, 16]
activation = "gelu"
solver = "adamw"
learning_rate = "cosine"
residual_connections = true
loss = "focal"
"""


VALID_WIDE_RANGE_MLP = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_wide_range"
model_family = "mlp"
[candidates.preprocessing]
normalization = "maxabs"
outlier_strategy = "clip_percentile"
outlier_quantile_low = 0.001
outlier_quantile_high = 0.999
projection = "pca"
projection_dim = 2048
[candidates.resampling]
strategy = "undersample_majority"
target_ratio = 2.0
[candidates.model]
hidden_dims = [128, 64, 32]
activation = "selu"
solver = "rmsprop"
input_noise_std = 12.0
hidden_noise_std = 8.0
weight_decay = 0.4
bias_weight_decay = 0.2
normalization_weight_decay = 0.15
learning_rate_init = 0.2
learning_rate = "linear_decay"
power_t = 12.0
batch_size = 1024
validation_fraction = 0.7
label_smoothing = 0.8
loss = "focal"
focal_gamma = 12.0
"""


INVALID_LBFGS_WITH_REPO_CONTROLS = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "mlp_bad_lbfgs_combo"
model_family = "mlp"
[candidates.preprocessing]
normalization = "robust"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32]
activation = "relu"
solver = "lbfgs"
normalization_layer = "layernorm"
weight_decay = 0.0005
learning_rate_init = 0.001
batch_size = 64
"""


INVALID_HIDDEN_DIMS = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "bad_mlp"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = []
activation = "relu"
"""


INVALID_OUTSIDE_ALLOWED_HIDDEN_DIMS = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "outside_allowed_set_mlp"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [256, 32]
activation = "relu"
"""


INVALID_TOO_DEEP_HIDDEN_DIMS = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "too_deep_mlp"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [128, 64, 32, 16, 32, 64]
activation = "relu"
"""


VALID_DUPLICATE_HIDDEN_DIMS = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "duplicate_width_mlp"
model_family = "mlp"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [64, 32, 64]
activation = "relu"
"""


class SubmissionValidationTests(unittest.TestCase):
    def write_fixture(self, root: Path, name: str, contents: str) -> Path:
        path = root / name
        path.write_text(contents.strip() + "\n", encoding="utf-8")
        return path

    def test_valid_submission_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(self.write_fixture(root, "submission.toml", VALID_SUBMISSION))

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.benchmark_id, "fashion_mnist_default")
            self.assertEqual(len(validated.candidates), 2)
            self.assertEqual(validated.candidates[0].model_family, "svm")
            self.assertEqual(validated.candidates[0].preprocessing["normalization"], "standard")
            self.assertEqual(
                validated.candidates[0].resampling["strategy"], "oversample_minority"
            )

    def test_rejects_legacy_top_level_notes(self) -> None:
        legacy_submission = """
benchmark = "fashion_mnist_default"
backend = "stub"
notes = "legacy memo"

[[candidates]]
name = "svm_balanced"
model_family = "svm"
[candidates.preprocessing]
normalization = "standard"
[candidates.resampling]
strategy = "none"
[candidates.model]
c = 1.0
kernel = "rbf"
"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with self.assertRaises(SubmissionLoadError) as ctx:
                load_submission(self.write_fixture(root, "submission.toml", legacy_submission))
            self.assertIn("unsupported top-level keys", str(ctx.exception))

    def test_rejects_too_many_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(self.write_fixture(root, "submission.toml", TOO_MANY_CANDIDATES))

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("max_candidates_per_submission", str(ctx.exception))

    def test_rejects_unknown_model_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(self.write_fixture(root, "submission.toml", UNKNOWN_FAMILY))

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("xgboost", str(ctx.exception))

    def test_rejects_unknown_preprocessing_choice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", INVALID_PREPROCESSING)
            )

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("normalization", str(ctx.exception))

    def test_rejects_svd_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", INVALID_SVD_PROJECTION)
            )

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("preprocessing.projection", str(ctx.exception))
            self.assertIn("pca", str(ctx.exception))

    def test_accepts_expanded_tree_and_svm_search_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_EXPANDED_TREE_SVM)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].preprocessing["projection"], "pca")
            self.assertEqual(validated.candidates[0].preprocessing["projection_dim"], 32)
            self.assertEqual(validated.candidates[0].preprocessing["outlier_strategy"], "clip_percentile")
            self.assertFalse(validated.candidates[0].model["shrinking"])
            self.assertEqual(validated.candidates[0].model["coef0"], 0.3)
            self.assertEqual(validated.candidates[1].preprocessing["projection"], "pca")
            self.assertTrue(validated.candidates[1].preprocessing["projection_whiten"])
            self.assertEqual(validated.candidates[1].model["criterion"], "log_loss")
            self.assertEqual(validated.candidates[1].model["max_leaf_nodes"], 32)
            self.assertEqual(validated.candidates[1].model["max_features"], 0.5)

    def test_accepts_expanded_mlp_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(self.write_fixture(root, "submission.toml", VALID_EXPANDED_MLP))

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].preprocessing["normalization"], "robust")
            self.assertEqual(validated.candidates[0].preprocessing["projection"], "pca")
            self.assertEqual(validated.candidates[0].resampling["strategy"], "oversample_minority")
            self.assertEqual(validated.candidates[0].model["hidden_dims"], [64, 32, 16])
            self.assertEqual(validated.candidates[0].model["normalization_layer"], "layernorm")
            self.assertEqual(validated.candidates[0].model["weight_decay"], 0.0005)
            self.assertEqual(validated.candidates[0].model["batch_size"], 64)
            self.assertEqual(validated.candidates[0].model["solver"], "adamw")
            self.assertEqual(validated.candidates[0].model["learning_rate"], "cosine")
            self.assertEqual(validated.candidates[0].model["loss"], "focal")

    def test_accepts_exotic_mlp_program_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_EXOTIC_MLP_PROGRAM)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].model["activation"], "gelu")
            self.assertEqual(validated.candidates[0].model["solver"], "adamw")
            self.assertTrue(validated.candidates[0].model["residual_connections"])
            self.assertEqual(validated.candidates[0].model["loss"], "focal")

    def test_rejects_lbfgs_with_repo_native_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", INVALID_LBFGS_WITH_REPO_CONTROLS)
            )

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("lbfgs", str(ctx.exception))

    def test_accepts_repo_native_mlp_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_MLP_REPO_NATIVE_CONTROLS)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].model["dropout_rate"], 0.2)

    def test_accepts_wider_numeric_search_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_WIDE_RANGE_MLP)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].preprocessing["projection_dim"], 2048)
            self.assertEqual(validated.candidates[0].resampling["target_ratio"], 2.0)
            self.assertEqual(validated.candidates[0].model["learning_rate_init"], 0.2)
            self.assertEqual(validated.candidates[0].model["weight_decay"], 0.4)
            self.assertEqual(validated.candidates[0].model["batch_size"], 1024)
            self.assertEqual(validated.candidates[0].model["focal_gamma"], 12.0)

    def test_accepts_mlp_outlier_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_MLP_OUTLIER_SEARCH)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].preprocessing["outlier_strategy"], "clip_zscore")
            self.assertEqual(validated.candidates[0].preprocessing["outlier_zscore_threshold"], 3.0)

    def test_accepts_mlp_projection_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_MLP_PROJECTION_SEARCH)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].preprocessing["projection"], "pca")
            self.assertEqual(validated.candidates[0].preprocessing["projection_dim"], 64)

    def test_accepts_mlp_resampling_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_MLP_RESAMPLING_SEARCH)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].resampling["strategy"], "oversample_minority")
            self.assertEqual(validated.candidates[0].resampling["target_ratio"], 1.0)

    def test_rejects_empty_hidden_dims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(self.write_fixture(root, "submission.toml", INVALID_HIDDEN_DIMS))

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("hidden_dims", str(ctx.exception))

    def test_rejects_hidden_dims_outside_allowed_width_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", INVALID_OUTSIDE_ALLOWED_HIDDEN_DIMS)
            )

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("must be one of", str(ctx.exception))

    def test_rejects_hidden_dims_deeper_than_four(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", INVALID_TOO_DEEP_HIDDEN_DIMS)
            )

            with self.assertRaises(SubmissionValidationError) as ctx:
                validate_submission(submission, catalog)

            self.assertIn("between 1 and 5 hidden layers", str(ctx.exception))

    def test_accepts_duplicate_hidden_dims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(
                self.write_fixture(root, "submission.toml", VALID_DUPLICATE_HIDDEN_DIMS)
            )

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].model["hidden_dims"], [64, 32, 64])

    def test_accepts_wider_and_deeper_hidden_dims(self) -> None:
        submission_text = """
benchmark = "fashion_mnist_default"
backend = "stub"

[[candidates]]
name = "wider_deeper_mlp"
model_family = "mlp"
[candidates.preprocessing]
normalization = "none"
outlier_strategy = "none"
[candidates.resampling]
strategy = "none"
[candidates.model]
hidden_dims = [128, 64, 32, 16, 16]
activation = "relu"
solver = "adam"
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            catalog = load_catalog(self.write_fixture(root, "catalog.toml", CATALOG_TEXT))
            submission = load_submission(self.write_fixture(root, "submission.toml", submission_text))

            validated = validate_submission(submission, catalog)

            self.assertEqual(validated.candidates[0].model["hidden_dims"], [128, 64, 32, 16, 16])

    def test_rejects_catalogs_with_misaligned_random_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with self.assertRaises(CatalogLoadError) as ctx:
                load_catalog(self.write_fixture(root, "catalog.toml", MISMATCHED_SEEDS_CATALOG))

            self.assertIn("common random_seed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
