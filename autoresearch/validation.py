from __future__ import annotations

from typing import Any

from autoresearch.catalog import Catalog
from autoresearch.domain import CandidateConfig, Submission, ValidatedSubmission


class SubmissionValidationError(ValueError):
    pass


ALLOWED_NORMALIZATIONS = {
    "none",
    "standard",
    "minmax",
    "maxabs",
    "robust",
    "l1",
    "l2",
    "mean_center",
    "signed_log1p",
}
ALLOWED_OUTLIER_STRATEGIES = {"none", "clip_iqr", "clip_zscore", "clip_percentile"}
ALLOWED_RESAMPLING_STRATEGIES = {"none", "oversample_minority", "undersample_majority"}
ALLOWED_PROJECTIONS = {"none", "pca"}
ALLOWED_HIDDEN_WIDTHS = {16, 32, 64, 128}
ALLOWED_MLP_ACTIVATIONS = {
    "identity",
    "relu",
    "tanh",
    "logistic",
    "leaky_relu",
    "elu",
    "softplus",
    "gelu",
    "selu",
}
ALLOWED_MLP_SOLVERS = {"lbfgs", "sgd", "adam", "adamw", "rmsprop"}
ALLOWED_MLP_NORMALIZATION_LAYERS = {"none", "layernorm", "batchnorm"}
ALLOWED_MLP_WEIGHT_INITS = {
    "auto",
    "xavier_uniform",
    "xavier_normal",
    "he_uniform",
    "he_normal",
    "lecun_uniform",
    "lecun_normal",
}
ALLOWED_MLP_LEARNING_RATES = {"constant", "invscaling", "adaptive", "cosine", "linear_decay"}
ALLOWED_MLP_LOSSES = {"cross_entropy", "focal"}
ALLOWED_MLP_PREPROCESSING_KEYS = {
    "normalization",
    "outlier_strategy",
    "outlier_iqr_multiplier",
    "outlier_zscore_threshold",
    "outlier_quantile_low",
    "outlier_quantile_high",
    "projection",
    "projection_dim",
    "projection_whiten",
}
ALLOWED_MLP_RESAMPLING_KEYS = {"strategy", "target_ratio"}
ALLOWED_MLP_MODEL_KEYS = {
    "hidden_dims",
    "hidden_dim1",
    "hidden_dim2",
    "activation",
    "activation_alpha",
    "weight_init",
    "use_bias",
    "input_noise_std",
    "hidden_noise_std",
    "solver",
    "normalization_layer",
    "normalization_epsilon",
    "normalization_momentum",
    "alpha",
    "weight_decay",
    "bias_weight_decay",
    "normalization_weight_decay",
    "learning_rate_init",
    "learning_rate",
    "min_learning_rate",
    "warmup_steps",
    "power_t",
    "momentum",
    "nesterovs_momentum",
    "beta_1",
    "beta_2",
    "epsilon",
    "tol",
    "max_iter",
    "batch_size",
    "early_stopping",
    "validation_fraction",
    "n_iter_no_change",
    "shuffle",
    "class_weight",
    "dropout_rate",
    "input_dropout_rate",
    "label_smoothing",
    "gradient_clip_norm",
    "residual_connections",
    "loss",
    "focal_gamma",
}
def _validate_float(name: str, value: Any, low: float, high: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SubmissionValidationError(f"{name} must be a float-like value.")
    converted = float(value)
    if not low <= converted <= high:
        raise SubmissionValidationError(f"{name} must be between {low} and {high}.")
    return converted


def _validate_int(name: str, value: Any, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SubmissionValidationError(f"{name} must be an integer.")
    if not low <= value <= high:
        raise SubmissionValidationError(f"{name} must be between {low} and {high}.")
    return value


def _validate_optional_int(name: str, value: Any, low: int, high: int) -> int | None:
    if value is None:
        return None
    return _validate_int(name, value, low, high)


def _validate_choice(name: str, value: Any, choices: set[str]) -> str:
    converted = str(value)
    if converted not in choices:
        raise SubmissionValidationError(f"{name} must be one of {sorted(choices)}.")
    return converted


def _validate_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise SubmissionValidationError(f"{name} must be true or false.")
    return value


def _validate_batch_size(name: str, value: Any) -> int | str:
    if isinstance(value, str):
        if value != "auto":
            raise SubmissionValidationError(f"{name} must be an integer or 'auto'.")
        return value
    return _validate_int(name, value, 4, 1024)


def _validate_discrete_int(name: str, value: Any, choices: set[int]) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SubmissionValidationError(f"{name} must be an integer.")
    if value not in choices:
        raise SubmissionValidationError(f"{name} must be one of {sorted(choices)}.")
    return value


def _reject_unknown_keys(section_name: str, raw: dict[str, Any], allowed_keys: set[str]) -> None:
    unknown = sorted(set(raw) - allowed_keys)
    if unknown:
        raise SubmissionValidationError(
            f"{section_name} contains unsupported keys {unknown}. "
            "Use the curated experiment surface instead of expanding the interface."
        )


def _validate_hidden_width(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SubmissionValidationError(f"{name} must be an integer.")
    if value not in ALLOWED_HIDDEN_WIDTHS:
        raise SubmissionValidationError(f"{name} must be one of {sorted(ALLOWED_HIDDEN_WIDTHS)}.")
    return value


def _validate_hidden_dims(name: str, value: Any) -> list[int]:
    if not isinstance(value, list):
        raise SubmissionValidationError(f"{name} must be an array of integers.")
    if len(value) < 1 or len(value) > 5:
        raise SubmissionValidationError(f"{name} must contain between 1 and 5 hidden layers.")
    return [_validate_hidden_width(f"{name}[{index}]", item) for index, item in enumerate(value, start=1)]


def _canonicalize_model_family(value: Any) -> str:
    return str(value).strip()


def _validate_class_weight(name: str, value: Any) -> str | dict[str, float]:
    if isinstance(value, str):
        if value != "balanced":
            raise SubmissionValidationError(f"{name} must be 'balanced' or a table of weights.")
        return value
    if not isinstance(value, dict) or not value:
        raise SubmissionValidationError(f"{name} must be 'balanced' or a non-empty table.")
    converted: dict[str, float] = {}
    for key, item in value.items():
        converted[str(key)] = _validate_float(f"{name}.{key}", item, 0.000001, 1000.0)
    return converted


def _validate_preprocessing(candidate: CandidateConfig) -> dict[str, Any]:
    raw = dict(candidate.preprocessing)
    if candidate.model_family == "mlp":
        _reject_unknown_keys("preprocessing", raw, ALLOWED_MLP_PREPROCESSING_KEYS)

    normalized = _validate_choice(
        "preprocessing.normalization",
        raw.get("normalization", "none"),
        ALLOWED_NORMALIZATIONS,
    )
    outlier_strategy = _validate_choice(
        "preprocessing.outlier_strategy",
        raw.get("outlier_strategy", "none"),
        ALLOWED_OUTLIER_STRATEGIES,
    )
    validated = {
        "normalization": normalized,
        "outlier_strategy": outlier_strategy,
    }
    if outlier_strategy == "clip_iqr":
        validated["outlier_iqr_multiplier"] = _validate_float(
            "preprocessing.outlier_iqr_multiplier",
            raw.get("outlier_iqr_multiplier", 1.5),
            0.5,
            25.0,
        )
    elif outlier_strategy == "clip_zscore":
        validated["outlier_zscore_threshold"] = _validate_float(
            "preprocessing.outlier_zscore_threshold",
            raw.get("outlier_zscore_threshold", 3.0),
            0.5,
            25.0,
        )
    elif outlier_strategy == "clip_percentile":
        low = _validate_float(
            "preprocessing.outlier_quantile_low",
            raw.get("outlier_quantile_low", 0.01),
            0.0,
            0.49,
        )
        high = _validate_float(
            "preprocessing.outlier_quantile_high",
            raw.get("outlier_quantile_high", 0.99),
            0.51,
            1.0,
        )
        if low >= high:
            raise SubmissionValidationError(
                "preprocessing.outlier_quantile_low must be smaller than preprocessing.outlier_quantile_high."
            )
        validated["outlier_quantile_low"] = low
        validated["outlier_quantile_high"] = high
    projection = _validate_choice(
        "preprocessing.projection",
        raw.get("projection", "none"),
        ALLOWED_PROJECTIONS,
    )
    validated["projection"] = projection
    if projection != "none":
        validated["projection_dim"] = _validate_int(
            "preprocessing.projection_dim",
            raw.get("projection_dim", 64),
            2,
            2048,
        )
        validated["projection_whiten"] = _validate_bool(
            "preprocessing.projection_whiten",
            raw.get("projection_whiten", False),
        )
    return validated


def _validate_resampling(candidate: CandidateConfig) -> dict[str, Any]:
    raw = dict(candidate.resampling)
    if candidate.model_family == "mlp":
        _reject_unknown_keys("resampling", raw, ALLOWED_MLP_RESAMPLING_KEYS)

    strategy = _validate_choice(
        "resampling.strategy",
        raw.get("strategy", "none"),
        ALLOWED_RESAMPLING_STRATEGIES,
    )
    validated = {"strategy": strategy}
    if strategy != "none":
        validated["target_ratio"] = _validate_float(
            "resampling.target_ratio",
            raw.get("target_ratio", 1.0),
            0.1,
            2.0,
        )
    return validated


def _validate_tree_model(raw: dict[str, Any]) -> dict[str, Any]:
    validated: dict[str, Any] = {}
    if "criterion" in raw:
        validated["criterion"] = _validate_choice(
            "model.criterion",
            raw["criterion"],
            {"gini", "entropy", "log_loss"},
        )
    if "splitter" in raw:
        validated["splitter"] = _validate_choice(
            "model.splitter",
            raw["splitter"],
            {"best", "random"},
        )
    if "max_depth" in raw:
        validated["max_depth"] = _validate_optional_int("model.max_depth", raw["max_depth"], 1, 256)
    if "min_samples_leaf" in raw:
        validated["min_samples_leaf"] = _validate_int("model.min_samples_leaf", raw["min_samples_leaf"], 1, 128)
    if "min_samples_split" in raw:
        validated["min_samples_split"] = _validate_int("model.min_samples_split", raw["min_samples_split"], 2, 128)
    if "class_weight" in raw:
        validated["class_weight"] = _validate_class_weight("model.class_weight", raw["class_weight"])
    if "max_features" in raw:
        max_features = raw["max_features"]
        if isinstance(max_features, str):
            validated["max_features"] = _validate_choice(
                "model.max_features",
                max_features,
                {"sqrt", "log2"},
            )
        elif isinstance(max_features, int) and not isinstance(max_features, bool):
            validated["max_features"] = _validate_int("model.max_features", max_features, 1, 4096)
        else:
            validated["max_features"] = _validate_float("model.max_features", max_features, 0.000001, 1.0)
    if "max_leaf_nodes" in raw:
        validated["max_leaf_nodes"] = _validate_optional_int("model.max_leaf_nodes", raw["max_leaf_nodes"], 2, 4096)
    if "min_impurity_decrease" in raw:
        validated["min_impurity_decrease"] = _validate_float(
            "model.min_impurity_decrease", raw["min_impurity_decrease"], 0.0, 100.0
        )
    if "ccp_alpha" in raw:
        validated["ccp_alpha"] = _validate_float("model.ccp_alpha", raw["ccp_alpha"], 0.0, 100.0)
    return validated


def _validate_svm_model(raw: dict[str, Any]) -> dict[str, Any]:
    validated: dict[str, Any] = {}
    if "c" in raw:
        validated["c"] = _validate_float("model.c", raw["c"], 0.0001, 1000.0)
    if "kernel" in raw:
        validated["kernel"] = _validate_choice(
            "model.kernel",
            raw["kernel"],
            {"linear", "rbf", "poly", "sigmoid"},
        )
    if "gamma" in raw:
        gamma = raw["gamma"]
        if isinstance(gamma, str):
            validated["gamma"] = _validate_choice("model.gamma", gamma, {"scale", "auto"})
        else:
            validated["gamma"] = _validate_float("model.gamma", gamma, 0.000001, 1000.0)
    if "degree" in raw:
        validated["degree"] = _validate_int("model.degree", raw["degree"], 2, 8)
    if "probability" in raw:
        validated["probability"] = _validate_bool("model.probability", raw["probability"])
    if "class_weight" in raw:
        validated["class_weight"] = _validate_class_weight("model.class_weight", raw["class_weight"])
    if "coef0" in raw:
        validated["coef0"] = _validate_float("model.coef0", raw["coef0"], -1000.0, 1000.0)
    if "tol" in raw:
        validated["tol"] = _validate_float("model.tol", raw["tol"], 0.000000001, 1.0)
    if "shrinking" in raw:
        validated["shrinking"] = _validate_bool("model.shrinking", raw["shrinking"])
    return validated


def _validate_mlp_model(raw: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys("model", raw, ALLOWED_MLP_MODEL_KEYS)
    validated: dict[str, Any] = {}

    if "hidden_dims" in raw and ("hidden_dim1" in raw or "hidden_dim2" in raw):
        raise SubmissionValidationError("Use either model.hidden_dims or legacy hidden_dim1/hidden_dim2, not both.")
    if "hidden_dims" in raw:
        validated["hidden_dims"] = _validate_hidden_dims("model.hidden_dims", raw["hidden_dims"])
    elif "hidden_dim1" in raw or "hidden_dim2" in raw:
        hidden_dims: list[int] = []
        if "hidden_dim1" in raw:
            hidden_dims.append(_validate_hidden_width("model.hidden_dim1", raw["hidden_dim1"]))
        if "hidden_dim2" in raw:
            hidden_dims.append(_validate_hidden_width("model.hidden_dim2", raw["hidden_dim2"]))
        validated["hidden_dims"] = hidden_dims

    if "activation" in raw:
        validated["activation"] = _validate_choice(
            "model.activation",
            raw["activation"],
            ALLOWED_MLP_ACTIVATIONS,
        )
    if "activation_alpha" in raw:
        validated["activation_alpha"] = _validate_float("model.activation_alpha", raw["activation_alpha"], 0.000001, 10.0)
    if "weight_init" in raw:
        validated["weight_init"] = _validate_choice("model.weight_init", raw["weight_init"], ALLOWED_MLP_WEIGHT_INITS)
    if "use_bias" in raw:
        validated["use_bias"] = _validate_bool("model.use_bias", raw["use_bias"])
    if "input_noise_std" in raw:
        validated["input_noise_std"] = _validate_float("model.input_noise_std", raw["input_noise_std"], 0.0, 25.0)
    if "hidden_noise_std" in raw:
        validated["hidden_noise_std"] = _validate_float("model.hidden_noise_std", raw["hidden_noise_std"], 0.0, 25.0)
    if "solver" in raw:
        validated["solver"] = _validate_choice(
            "model.solver",
            raw["solver"],
            ALLOWED_MLP_SOLVERS,
        )
    if "normalization_layer" in raw:
        validated["normalization_layer"] = _validate_choice(
            "model.normalization_layer",
            raw["normalization_layer"],
            ALLOWED_MLP_NORMALIZATION_LAYERS,
        )
    if "normalization_epsilon" in raw:
        validated["normalization_epsilon"] = _validate_float(
            "model.normalization_epsilon", raw["normalization_epsilon"], 1e-12, 1.0
        )
    if "normalization_momentum" in raw:
        validated["normalization_momentum"] = _validate_float(
            "model.normalization_momentum", raw["normalization_momentum"], 0.0, 1.0
        )
    if "alpha" in raw and "weight_decay" in raw:
        raise SubmissionValidationError("Use either model.weight_decay or legacy model.alpha, not both.")
    if "weight_decay" in raw:
        validated["weight_decay"] = _validate_float("model.weight_decay", raw["weight_decay"], 0.0, 1.0)
    elif "alpha" in raw:
        validated["weight_decay"] = _validate_float("model.alpha", raw["alpha"], 0.0, 1.0)
    if "bias_weight_decay" in raw:
        validated["bias_weight_decay"] = _validate_float("model.bias_weight_decay", raw["bias_weight_decay"], 0.0, 1.0)
    if "normalization_weight_decay" in raw:
        validated["normalization_weight_decay"] = _validate_float(
            "model.normalization_weight_decay", raw["normalization_weight_decay"], 0.0, 1.0
        )
    if "learning_rate_init" in raw:
        validated["learning_rate_init"] = _validate_float(
            "model.learning_rate_init", raw["learning_rate_init"], 0.000001, 1.0
        )
    if "learning_rate" in raw:
        validated["learning_rate"] = _validate_choice(
            "model.learning_rate",
            raw["learning_rate"],
            ALLOWED_MLP_LEARNING_RATES,
        )
    if "min_learning_rate" in raw:
        validated["min_learning_rate"] = _validate_float(
            "model.min_learning_rate", raw["min_learning_rate"], 1e-12, 1.0
        )
    if "warmup_steps" in raw:
        validated["warmup_steps"] = _validate_int("model.warmup_steps", raw["warmup_steps"], 0, 1_000_000)
    if "power_t" in raw:
        validated["power_t"] = _validate_float("model.power_t", raw["power_t"], 0.0, 20.0)
    if "momentum" in raw:
        validated["momentum"] = _validate_float("model.momentum", raw["momentum"], 0.0, 1.0)
    if "nesterovs_momentum" in raw:
        validated["nesterovs_momentum"] = _validate_bool("model.nesterovs_momentum", raw["nesterovs_momentum"])
    if "beta_1" in raw:
        validated["beta_1"] = _validate_float("model.beta_1", raw["beta_1"], 0.0, 1.0)
    if "beta_2" in raw:
        validated["beta_2"] = _validate_float("model.beta_2", raw["beta_2"], 0.0, 1.0)
    if "epsilon" in raw:
        validated["epsilon"] = _validate_float("model.epsilon", raw["epsilon"], 1e-12, 1.0)
    if "tol" in raw:
        validated["tol"] = _validate_float("model.tol", raw["tol"], 1e-12, 1.0)
    if "max_iter" in raw:
        validated["max_iter"] = _validate_int("model.max_iter", raw["max_iter"], 1, 100000)
    if "batch_size" in raw:
        validated["batch_size"] = _validate_batch_size("model.batch_size", raw["batch_size"])
    if "early_stopping" in raw:
        validated["early_stopping"] = _validate_bool("model.early_stopping", raw["early_stopping"])
    if "validation_fraction" in raw:
        validated["validation_fraction"] = _validate_float(
            "model.validation_fraction", raw["validation_fraction"], 0.01, 0.8
        )
    if "n_iter_no_change" in raw:
        validated["n_iter_no_change"] = _validate_int("model.n_iter_no_change", raw["n_iter_no_change"], 1, 100000)
    if "shuffle" in raw:
        validated["shuffle"] = _validate_bool("model.shuffle", raw["shuffle"])
    if "class_weight" in raw:
        validated["class_weight"] = _validate_class_weight("model.class_weight", raw["class_weight"])
    if "dropout_rate" in raw:
        validated["dropout_rate"] = _validate_float("model.dropout_rate", raw["dropout_rate"], 0.0, 0.95)
    if "input_dropout_rate" in raw:
        validated["input_dropout_rate"] = _validate_float(
            "model.input_dropout_rate", raw["input_dropout_rate"], 0.0, 0.95
        )
    if "label_smoothing" in raw:
        validated["label_smoothing"] = _validate_float("model.label_smoothing", raw["label_smoothing"], 0.0, 0.9)
    if "gradient_clip_norm" in raw:
        validated["gradient_clip_norm"] = _validate_float(
            "model.gradient_clip_norm", raw["gradient_clip_norm"], 1e-6, 1_000_000.0
        )
    if "residual_connections" in raw:
        validated["residual_connections"] = _validate_bool("model.residual_connections", raw["residual_connections"])
    if "loss" in raw:
        validated["loss"] = _validate_choice("model.loss", raw["loss"], ALLOWED_MLP_LOSSES)
    if "focal_gamma" in raw:
        validated["focal_gamma"] = _validate_float("model.focal_gamma", raw["focal_gamma"], 0.0, 20.0)

    uses_repo_only_path = (
        validated.get("activation", raw.get("activation", "relu")) not in {"identity", "relu", "tanh", "logistic"}
        or validated.get("solver", raw.get("solver", "adam")) not in {"lbfgs", "sgd", "adam"}
        or validated.get("normalization_layer", raw.get("normalization_layer", "none")) != "none"
        or validated.get("learning_rate", raw.get("learning_rate", "constant")) not in {"constant", "invscaling", "adaptive"}
        or any(
            key in validated
            for key in {
                "bias_weight_decay",
                "normalization_weight_decay",
                "normalization_momentum",
                "min_learning_rate",
                "warmup_steps",
                "dropout_rate",
                "input_dropout_rate",
                "label_smoothing",
                "gradient_clip_norm",
                "residual_connections",
                "focal_gamma",
                "activation_alpha",
                "weight_init",
                "use_bias",
                "input_noise_std",
                "hidden_noise_std",
            }
        )
        or validated.get("loss", raw.get("loss", "cross_entropy")) != "cross_entropy"
    )
    if validated.get("solver", raw.get("solver", "adam")) == "lbfgs" and uses_repo_only_path:
        raise SubmissionValidationError(
            "model.solver='lbfgs' cannot be combined with repo-native MLP controls; "
            "use adam/sgd for expanded MLP search."
        )
    return validated


def _validate_model(candidate: CandidateConfig) -> dict[str, Any]:
    raw = dict(candidate.model)
    if candidate.model_family == "tree":
        return _validate_tree_model(raw)
    if candidate.model_family == "svm":
        return _validate_svm_model(raw)
    if candidate.model_family == "mlp":
        return _validate_mlp_model(raw)
    raise SubmissionValidationError(f"Unknown model family {candidate.model_family!r}.")


def _validate_candidate(candidate: CandidateConfig) -> CandidateConfig:
    canonical_family = _canonicalize_model_family(candidate.model_family)
    canonical_candidate = CandidateConfig(
        name=candidate.name,
        model_family=canonical_family,
        preprocessing=dict(candidate.preprocessing),
        resampling=dict(candidate.resampling),
        model=dict(candidate.model),
    )
    validated_preprocessing = _validate_preprocessing(canonical_candidate)
    validated_resampling = _validate_resampling(canonical_candidate)
    validated_model = _validate_model(canonical_candidate)
    return CandidateConfig(
        name=candidate.name,
        model_family=canonical_family,
        preprocessing=validated_preprocessing,
        resampling=validated_resampling,
        model=validated_model,
    )


def validate_submission(submission: Submission, catalog: Catalog) -> ValidatedSubmission:
    benchmark = catalog.benchmark(submission.benchmark_id)
    dataset = catalog.dataset(benchmark.dataset_id)

    if submission.backend != benchmark.backend:
        raise SubmissionValidationError(
            f"Submission backend {submission.backend!r} does not match benchmark backend "
            f"{benchmark.backend!r}."
        )

    if len(submission.candidates) > benchmark.max_candidates_per_submission:
        raise SubmissionValidationError(
            "Submission exceeds max_candidates_per_submission="
            f"{benchmark.max_candidates_per_submission}."
        )

    names = [candidate.name for candidate in submission.candidates]
    if len(names) != len(set(names)):
        raise SubmissionValidationError("Candidate names must be unique within a submission.")

    validated_candidates: list[CandidateConfig] = []
    allowed_families = set(benchmark.allowed_model_families)
    for candidate in submission.candidates:
        validated = _validate_candidate(candidate)
        if validated.model_family not in allowed_families:
            raise SubmissionValidationError(
                f"Candidate {validated.name!r} uses model family {validated.model_family!r}, "
                f"which is not allowed for benchmark {benchmark.benchmark_id!r}."
            )
        validated_candidates.append(validated)

    return ValidatedSubmission(
        benchmark_id=submission.benchmark_id,
        backend=submission.backend,
        benchmark=benchmark,
        dataset=dataset,
        candidates=tuple(validated_candidates),
        source_path=submission.source_path,
    )
