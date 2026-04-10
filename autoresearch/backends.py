from __future__ import annotations

from collections import Counter
import csv
import hashlib
import inspect
import math
from pathlib import Path
import sys
from typing import Any

from autoresearch.domain import BenchmarkSpec, CandidateConfig, CandidateResult, DatasetSpec


class BackendError(RuntimeError):
    pass


def make_backend(name: str, root: Path) -> "TrainingBackend":
    normalized = name.strip().lower()
    if normalized == "stub":
        return StubBackend(root)
    if normalized == "sklearn":
        return SklearnBackend(root)
    raise BackendError(f"Unknown backend {name!r}.")


class TrainingBackend:
    backend_name = "base"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def evaluate(
        self,
        benchmark: BenchmarkSpec,
        dataset: DatasetSpec,
        candidate: CandidateConfig,
    ) -> CandidateResult:
        raise NotImplementedError


class StubBackend(TrainingBackend):
    backend_name = "stub"

    FAMILY_PRIORS: dict[tuple[str, str], float] = {
        ("fashion_mnist", "tree"): 0.782,
        ("fashion_mnist", "svm"): 0.842,
        ("fashion_mnist", "mlp"): 0.851,
        ("cifar10", "tree"): 0.224,
        ("cifar10", "svm"): 0.418,
        ("cifar10", "mlp"): 0.486,
        ("sms_spam", "svm"): 0.972,
        ("sms_spam", "mlp"): 0.964,
        ("twenty_newsgroups", "tree"): 0.355,
        ("twenty_newsgroups", "svm"): 0.794,
        ("twenty_newsgroups", "mlp"): 0.736,
    }

    IDEALS: dict[tuple[str, str], dict[str, Any]] = {
        ("fashion_mnist", "svm"): {
            "preprocessing": {"normalization": "minmax", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"c": 10.0, "kernel": "rbf", "gamma": "scale"},
        },
        ("fashion_mnist", "tree"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"criterion": "gini", "max_depth": 18, "min_samples_leaf": 1},
        },
        ("fashion_mnist", "mlp"): {
            "preprocessing": {"normalization": "minmax", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"hidden_dim1": 64, "hidden_dim2": 32, "activation": "relu", "alpha": 0.0005},
        },
        ("cifar10", "svm"): {
            "preprocessing": {"normalization": "maxabs", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"c": 3.0, "kernel": "rbf", "gamma": "scale"},
        },
        ("cifar10", "tree"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"criterion": "gini", "max_depth": 18, "min_samples_leaf": 1},
        },
        ("cifar10", "mlp"): {
            "preprocessing": {"normalization": "maxabs", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"hidden_dim1": 64, "hidden_dim2": 64, "activation": "relu", "alpha": 0.0005},
        },
        ("sms_spam", "svm"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"c": 1.0, "kernel": "linear", "class_weight": "balanced"},
        },
        ("sms_spam", "mlp"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"hidden_dim1": 64, "hidden_dim2": 32, "activation": "relu", "alpha": 0.0005},
        },
        ("twenty_newsgroups", "svm"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"c": 1.0, "kernel": "linear", "class_weight": "balanced"},
        },
        ("twenty_newsgroups", "tree"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"criterion": "entropy", "max_depth": 32, "min_samples_leaf": 2},
        },
        ("twenty_newsgroups", "mlp"): {
            "preprocessing": {"normalization": "none", "outlier_strategy": "none"},
            "resampling": {"strategy": "none"},
            "model": {"hidden_dim1": 64, "hidden_dim2": 32, "activation": "relu", "alpha": 0.0005},
        },
    }

    def _noise(self, key: str) -> float:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    def _score_section(self, ideal: dict[str, Any], actual: dict[str, Any]) -> float:
        bonus = 0.0
        for key, target in ideal.items():
            actual_value = actual.get(key)
            if actual_value is None:
                bonus -= 0.005
                continue
            if isinstance(target, str):
                bonus += 0.012 if str(actual_value) == target else -0.01
            elif isinstance(target, (int, float)):
                delta = abs(float(actual_value) - float(target))
                scale = max(abs(float(target)), 1.0)
                proximity = max(0.0, 1.0 - delta / scale)
                bonus += 0.018 * proximity - 0.004
            elif isinstance(target, dict):
                bonus += self._score_section(target, actual_value if isinstance(actual_value, dict) else {})
        return bonus

    def _estimate_overfit_penalty(self, candidate: CandidateConfig) -> float:
        model = candidate.model
        penalty = 0.003
        if candidate.model_family == "tree":
            depth = float(model.get("max_depth", 12) or 12)
            min_leaf = float(model.get("min_samples_leaf", 1))
            penalty += max(0.0, depth - 8.0) * 0.0012
            penalty += 0.004 if min_leaf <= 1 else 0.0
        elif candidate.model_family == "svm":
            c_value = float(model.get("c", 1.0))
            penalty += max(0.0, math.log10(c_value + 1e-9) - 0.2) * 0.004
            penalty += 0.006 if str(model.get("kernel", "rbf")) == "poly" else 0.0
        elif candidate.model_family == "mlp":
            hidden_dims = model.get("hidden_dims")
            if isinstance(hidden_dims, list) and hidden_dims:
                total_hidden = float(sum(int(item) for item in hidden_dims))
            else:
                total_hidden = float(model.get("hidden_dim1", 64)) + float(model.get("hidden_dim2", 32))
            penalty += max(0.0, (total_hidden - 256.0) / 256.0) * 0.01
            penalty += 0.004 if not bool(model.get("early_stopping", True)) else 0.0
        strategy = str(candidate.resampling.get("strategy", "none"))
        if strategy == "oversample_minority":
            penalty += 0.003
        return penalty

    def evaluate(
        self,
        benchmark: BenchmarkSpec,
        dataset: DatasetSpec,
        candidate: CandidateConfig,
    ) -> CandidateResult:
        base = self.FAMILY_PRIORS.get((dataset.dataset_id, candidate.model_family), 0.74)
        ideal = self.IDEALS.get((dataset.dataset_id, candidate.model_family), {})
        bonus = 0.0
        bonus += self._score_section(ideal.get("preprocessing", {}), candidate.preprocessing)
        bonus += self._score_section(ideal.get("resampling", {}), candidate.resampling)
        bonus += self._score_section(ideal.get("model", {}), candidate.model)

        signature = (
            f"{dataset.dataset_id}:{candidate.model_family}:{candidate.preprocessing}:"
            f"{candidate.resampling}:{candidate.model}"
        )
        val_noise = (self._noise(signature + ":val") - 0.5) * 0.008
        test_noise = (self._noise(signature + ":test") - 0.5) * 0.004
        validation_score = max(0.5, min(0.999, base + bonus + val_noise))
        test_score = max(
            0.5,
            min(0.999, validation_score - self._estimate_overfit_penalty(candidate) + test_noise),
        )
        summary = (
            f"Stub {candidate.model_family} with normalization={candidate.preprocessing.get('normalization', 'none')}, "
            f"outlier={candidate.preprocessing.get('outlier_strategy', 'none')}, "
            f"resampling={candidate.resampling.get('strategy', 'none')}."
        )
        return CandidateResult(
            candidate_name=candidate.name,
            model_family=candidate.model_family,
            metric=benchmark.metric,
            validation_score=round(validation_score, 6),
            test_score=round(test_score, 6),
            rank=0,
            backend_name=self.backend_name,
            summary=summary,
            preprocessing=dict(candidate.preprocessing),
            resampling=dict(candidate.resampling),
            model=dict(candidate.model),
        )


class SklearnBackend(TrainingBackend):
    backend_name = "sklearn"

    def _require_sklearn(self) -> dict[str, Any]:
        try:
            import numpy as np
            from sklearn.decomposition import PCA, TruncatedSVD
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.preprocessing import LabelEncoder
            from sklearn.metrics import accuracy_score
            from sklearn.model_selection import train_test_split
            from sklearn.neural_network import MLPClassifier
            from sklearn.svm import SVC
            from sklearn.tree import DecisionTreeClassifier
        except ModuleNotFoundError as exc:
            raise BackendError(
                "The sklearn backend requires numpy and scikit-learn to be installed. "
                "Use backend='stub' for the dependency-free meta experiment."
            ) from exc

        return {
            "np": np,
            "PCA": PCA,
            "TfidfVectorizer": TfidfVectorizer,
            "TruncatedSVD": TruncatedSVD,
            "LabelEncoder": LabelEncoder,
            "accuracy_score": accuracy_score,
            "train_test_split": train_test_split,
            "MLPClassifier": MLPClassifier,
            "SVC": SVC,
            "DecisionTreeClassifier": DecisionTreeClassifier,
        }

    def _resolve_path(self, relative_path: str) -> Path:
        return (self.root / relative_path).resolve()

    def _load_dataset(self, dataset: DatasetSpec, libs: dict[str, Any]) -> tuple[Any, list[Any], str]:
        if dataset.kind == "csv_text_classification":
            dataset_path = self._resolve_path(str(dataset.options["path"]))
            target_column = str(dataset.options["target_column"])
            text_column = str(dataset.options["text_column"])
            if not dataset_path.exists():
                raise BackendError(f"Dataset file not found: {dataset_path}")
            csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
            texts: list[str] = []
            labels: list[Any] = []
            with dataset_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    labels.append(row[target_column])
                    texts.append(row[text_column])
            max_samples = dataset.options.get("max_samples")
            if isinstance(max_samples, int) and max_samples > 0 and max_samples < len(labels):
                sample_seed = int(dataset.options.get("sample_seed", 42))
                train_test_split = libs["train_test_split"]
                texts, _, labels, _ = train_test_split(
                    texts,
                    labels,
                    train_size=max_samples,
                    random_state=sample_seed,
                    stratify=labels,
                )
            return texts, labels, "text"

        if dataset.kind == "npz_classification":
            dataset_path = self._resolve_path(str(dataset.options["path"]))
            if not dataset_path.exists():
                raise BackendError(f"Dataset file not found: {dataset_path}")
            np = libs["np"]
            with np.load(dataset_path) as data:
                features = data[str(dataset.options.get("features_key", "x"))]
                labels = data[str(dataset.options.get("target_key", "y"))]
            max_samples = dataset.options.get("max_samples")
            if isinstance(max_samples, int) and max_samples > 0 and max_samples < len(labels):
                sample_seed = int(dataset.options.get("sample_seed", 42))
                train_test_split = libs["train_test_split"]
                features, _, labels, _ = train_test_split(
                    features,
                    labels,
                    train_size=max_samples,
                    random_state=sample_seed,
                    stratify=labels,
                )
            if len(features.shape) > 2:
                features = features.reshape((features.shape[0], math.prod(features.shape[1:])))
            return features, labels.tolist(), "array"

        raise BackendError(f"Unsupported dataset kind {dataset.kind!r}.")

    def _split_dataset(
        self,
        features: Any,
        labels: list[Any],
        benchmark: BenchmarkSpec,
        libs: dict[str, Any],
    ) -> tuple[Any, Any, Any, list[Any], list[Any], list[Any]]:
        train_test_split = libs["train_test_split"]
        x_train_val, x_test, y_train_val, y_test = train_test_split(
            features,
            labels,
            test_size=benchmark.test_size,
            random_state=benchmark.random_seed,
            stratify=labels,
        )
        adjusted_validation_size = benchmark.validation_size / (1.0 - benchmark.test_size)
        x_train, x_val, y_train, y_val = train_test_split(
            x_train_val,
            y_train_val,
            test_size=adjusted_validation_size,
            random_state=benchmark.random_seed + 1,
            stratify=y_train_val,
        )
        return x_train, x_val, x_test, y_train, y_val, y_test

    def _vectorize_features(
        self,
        dataset: DatasetSpec,
        feature_kind: str,
        x_train: Any,
        x_val: Any,
        x_test: Any,
        libs: dict[str, Any],
    ) -> tuple[Any, Any, Any]:
        np = libs["np"]
        if feature_kind == "text":
            vectorizer = libs["TfidfVectorizer"](
                max_features=int(dataset.options.get("max_features", 2000)),
                ngram_range=(1, int(dataset.options.get("ngram_max", 2))),
                min_df=int(dataset.options.get("min_df", 2)),
                strip_accents="unicode",
                lowercase=True,
                sublinear_tf=True,
                dtype=np.float32,
            )
            train_array = vectorizer.fit_transform(x_train).toarray()
            val_array = vectorizer.transform(x_val).toarray()
            test_array = vectorizer.transform(x_test).toarray()
        else:
            train_array = np.asarray(x_train, dtype=float)
            val_array = np.asarray(x_val, dtype=float)
            test_array = np.asarray(x_test, dtype=float)
        if train_array.ndim > 2:
            train_array = train_array.reshape((train_array.shape[0], math.prod(train_array.shape[1:])))
            val_array = val_array.reshape((val_array.shape[0], math.prod(val_array.shape[1:])))
            test_array = test_array.reshape((test_array.shape[0], math.prod(test_array.shape[1:])))
        return train_array, val_array, test_array

    def _apply_outlier_strategy(
        self,
        x_train: Any,
        x_val: Any,
        x_test: Any,
        preprocessing: dict[str, Any],
        libs: dict[str, Any],
    ) -> tuple[Any, Any, Any]:
        np = libs["np"]
        strategy = str(preprocessing.get("outlier_strategy", "none"))
        if strategy == "none":
            return x_train, x_val, x_test

        if strategy == "clip_iqr":
            q1 = np.percentile(x_train, 25, axis=0)
            q3 = np.percentile(x_train, 75, axis=0)
            iqr = q3 - q1
            multiplier = float(preprocessing.get("outlier_iqr_multiplier", 1.5))
            low = q1 - multiplier * iqr
            high = q3 + multiplier * iqr
        elif strategy == "clip_zscore":
            mean = np.mean(x_train, axis=0)
            std = np.std(x_train, axis=0)
            std = np.where(std == 0, 1.0, std)
            threshold = float(preprocessing.get("outlier_zscore_threshold", 3.0))
            low = mean - threshold * std
            high = mean + threshold * std
        elif strategy == "clip_percentile":
            low = np.quantile(x_train, float(preprocessing.get("outlier_quantile_low", 0.01)), axis=0)
            high = np.quantile(x_train, float(preprocessing.get("outlier_quantile_high", 0.99)), axis=0)
        else:
            raise BackendError(f"Unsupported outlier strategy {strategy!r}.")

        return (
            np.clip(x_train, low, high),
            np.clip(x_val, low, high),
            np.clip(x_test, low, high),
        )

    def _apply_normalization(
        self,
        x_train: Any,
        x_val: Any,
        x_test: Any,
        preprocessing: dict[str, Any],
        libs: dict[str, Any],
    ) -> tuple[Any, Any, Any]:
        np = libs["np"]
        normalization = str(preprocessing.get("normalization", "none"))
        if normalization == "none":
            return x_train, x_val, x_test
        if normalization == "standard":
            mean = np.mean(x_train, axis=0)
            std = np.std(x_train, axis=0)
            std = np.where(std == 0, 1.0, std)
            return ((x_train - mean) / std, (x_val - mean) / std, (x_test - mean) / std)
        if normalization == "minmax":
            low = np.min(x_train, axis=0)
            high = np.max(x_train, axis=0)
            denom = np.where(high - low == 0, 1.0, high - low)
            return (
                (x_train - low) / denom,
                (x_val - low) / denom,
                (x_test - low) / denom,
            )
        if normalization == "maxabs":
            scale = np.max(np.abs(x_train), axis=0)
            scale = np.where(scale == 0, 1.0, scale)
            return (x_train / scale, x_val / scale, x_test / scale)
        if normalization == "robust":
            median = np.median(x_train, axis=0)
            q1 = np.percentile(x_train, 25, axis=0)
            q3 = np.percentile(x_train, 75, axis=0)
            iqr = np.where(q3 - q1 == 0, 1.0, q3 - q1)
            return ((x_train - median) / iqr, (x_val - median) / iqr, (x_test - median) / iqr)
        if normalization == "mean_center":
            mean = np.mean(x_train, axis=0)
            return (x_train - mean, x_val - mean, x_test - mean)
        if normalization == "signed_log1p":
            def _signed_log(array: Any) -> Any:
                return np.sign(array) * np.log1p(np.abs(array))

            return (_signed_log(x_train), _signed_log(x_val), _signed_log(x_test))
        if normalization == "l1":
            def _row_l1_scale(array: Any) -> Any:
                denom = np.sum(np.abs(array), axis=1, keepdims=True)
                denom = np.where(denom == 0, 1.0, denom)
                return array / denom

            return (_row_l1_scale(x_train), _row_l1_scale(x_val), _row_l1_scale(x_test))
        if normalization == "l2":
            def _row_l2_scale(array: Any) -> Any:
                denom = np.linalg.norm(array, axis=1, keepdims=True)
                denom = np.where(denom == 0, 1.0, denom)
                return array / denom

            return (_row_l2_scale(x_train), _row_l2_scale(x_val), _row_l2_scale(x_test))
        raise BackendError(f"Unsupported normalization {normalization!r}.")

    def _apply_projection(
        self,
        x_train: Any,
        x_val: Any,
        x_test: Any,
        preprocessing: dict[str, Any],
        libs: dict[str, Any],
    ) -> tuple[Any, Any, Any]:
        projection = str(preprocessing.get("projection", "none"))
        if projection == "none":
            return x_train, x_val, x_test

        projection_dim = int(preprocessing.get("projection_dim", 64))
        if projection == "pca":
            max_components = max(1, min(x_train.shape[0] - 1, x_train.shape[1]))
            projector = libs["PCA"](
                n_components=min(projection_dim, max_components),
                whiten=bool(preprocessing.get("projection_whiten", False)),
                random_state=42,
            )
        elif projection == "svd":
            max_components = max(1, min(x_train.shape[0] - 1, x_train.shape[1] - 1))
            projector = libs["TruncatedSVD"](
                n_components=min(projection_dim, max_components),
                random_state=42,
            )
        else:
            raise BackendError(f"Unsupported projection {projection!r}.")

        return (
            projector.fit_transform(x_train),
            projector.transform(x_val),
            projector.transform(x_test),
        )

    def _resolve_hidden_layer_sizes(self, model: dict[str, Any]) -> tuple[int, ...]:
        hidden_dims = model.get("hidden_dims")
        if isinstance(hidden_dims, list) and hidden_dims:
            return tuple(int(item) for item in hidden_dims)
        return (
            int(model.get("hidden_dim1", 64)),
            int(model.get("hidden_dim2", 32)),
        )

    def _should_use_repo_mlp(self, model: dict[str, Any]) -> bool:
        return (
            str(model.get("activation", "relu")) not in {"identity", "relu", "tanh", "logistic"}
            or str(model.get("solver", "adam")) not in {"lbfgs", "sgd", "adam"}
            or str(model.get("normalization_layer", "none")) != "none"
            or str(model.get("learning_rate", "constant")) not in {"constant", "invscaling", "adaptive"}
            or "bias_weight_decay" in model
            or "normalization_weight_decay" in model
            or "normalization_momentum" in model
            or "min_learning_rate" in model
            or "warmup_steps" in model
            or "dropout_rate" in model
            or "input_dropout_rate" in model
            or "label_smoothing" in model
            or "gradient_clip_norm" in model
            or "residual_connections" in model
            or str(model.get("loss", "cross_entropy")) != "cross_entropy"
            or "focal_gamma" in model
            or "activation_alpha" in model
            or "weight_init" in model
            or "use_bias" in model
            or "input_noise_std" in model
            or "hidden_noise_std" in model
        )

    def _resample_training_data(
        self,
        x_train: Any,
        y_train: list[Any],
        resampling: dict[str, Any],
        seed: int,
        libs: dict[str, Any],
    ) -> tuple[Any, list[Any]]:
        np = libs["np"]
        strategy = str(resampling.get("strategy", "none"))
        if strategy == "none":
            return x_train, y_train

        rng = np.random.default_rng(seed)
        y_array = np.asarray(y_train)
        classes, counts = np.unique(y_array, return_counts=True)
        index_chunks: list[Any] = []

        if strategy == "oversample_minority":
            desired_count = int(math.ceil(int(counts.max()) * float(resampling.get("target_ratio", 1.0))))
            for class_label, count in zip(classes, counts):
                class_indices = np.where(y_array == class_label)[0]
                if int(count) >= desired_count:
                    index_chunks.append(class_indices)
                    continue
                extra = rng.choice(class_indices, size=desired_count - int(count), replace=True)
                index_chunks.append(np.concatenate([class_indices, extra]))
        elif strategy == "undersample_majority":
            target_ratio = float(resampling.get("target_ratio", 1.0))
            max_allowed = int(math.ceil(int(counts.min()) / target_ratio))
            for class_label in classes:
                class_indices = np.where(y_array == class_label)[0]
                if len(class_indices) > max_allowed:
                    class_indices = rng.choice(class_indices, size=max_allowed, replace=False)
                index_chunks.append(class_indices)
        else:
            raise BackendError(f"Unsupported resampling strategy {strategy!r}.")

        sampled_indices = np.concatenate(index_chunks)
        rng.shuffle(sampled_indices)
        resampled_y = y_array[sampled_indices].tolist()
        return x_train[sampled_indices], resampled_y

    def _compute_sample_weight(
        self,
        y_train: list[Any],
        class_weight: Any,
        libs: dict[str, Any],
    ) -> Any:
        if class_weight is None:
            return None
        np = libs["np"]
        if class_weight == "balanced":
            counts = Counter(y_train)
            total = float(len(y_train))
            n_classes = float(len(counts))
            mapping = {
                label: total / (n_classes * count)
                for label, count in counts.items()
            }
        elif isinstance(class_weight, dict):
            mapping = {str(key): float(value) for key, value in class_weight.items()}
        else:
            raise BackendError(f"Unsupported class_weight value: {class_weight!r}")
        return np.asarray(
            [mapping.get(label, mapping.get(str(label), 1.0)) for label in y_train],
            dtype=float,
        )

    def _make_estimator(self, libs: dict[str, Any], candidate: CandidateConfig, seed: int) -> Any:
        model = dict(candidate.model)
        if candidate.model_family == "tree":
            return libs["DecisionTreeClassifier"](
                criterion=str(model.get("criterion", "gini")),
                splitter=str(model.get("splitter", "best")),
                max_depth=model.get("max_depth"),
                min_samples_leaf=int(model.get("min_samples_leaf", 1)),
                min_samples_split=int(model.get("min_samples_split", 2)),
                class_weight=model.get("class_weight"),
                max_features=model.get("max_features"),
                max_leaf_nodes=model.get("max_leaf_nodes"),
                min_impurity_decrease=float(model.get("min_impurity_decrease", 0.0)),
                ccp_alpha=float(model.get("ccp_alpha", 0.0)),
                random_state=seed,
            )
        if candidate.model_family == "svm":
            return libs["SVC"](
                C=float(model.get("c", 1.0)),
                kernel=str(model.get("kernel", "rbf")),
                gamma=model.get("gamma", "scale"),
                degree=int(model.get("degree", 3)),
                coef0=float(model.get("coef0", 0.0)),
                tol=float(model.get("tol", 1e-3)),
                shrinking=bool(model.get("shrinking", True)),
                probability=bool(model.get("probability", False)),
                class_weight=model.get("class_weight"),
                random_state=seed,
            )
        if candidate.model_family == "mlp":
            if self._should_use_repo_mlp(model):
                from autoresearch.repo_mlp import RepoMLPClassifier

                return RepoMLPClassifier(
                    hidden_layer_sizes=self._resolve_hidden_layer_sizes(model),
                    activation=str(model.get("activation", "relu")),
                    activation_alpha=float(model.get("activation_alpha", 0.01)),
                    weight_init=str(model.get("weight_init", "auto")),
                    use_bias=bool(model.get("use_bias", True)),
                    input_noise_std=float(model.get("input_noise_std", 0.0)),
                    hidden_noise_std=float(model.get("hidden_noise_std", 0.0)),
                    solver=str(model.get("solver", "adam")),
                    alpha=float(model.get("alpha", 0.0005)),
                    weight_decay=model.get("weight_decay"),
                    bias_weight_decay=float(model.get("bias_weight_decay", 0.0)),
                    normalization_weight_decay=float(model.get("normalization_weight_decay", 0.0)),
                    normalization_layer=str(model.get("normalization_layer", "none")),
                    normalization_epsilon=float(model.get("normalization_epsilon", 1e-5)),
                    normalization_momentum=float(model.get("normalization_momentum", 0.1)),
                    dropout_rate=float(model.get("dropout_rate", 0.0)),
                    input_dropout_rate=float(model.get("input_dropout_rate", 0.0)),
                    label_smoothing=float(model.get("label_smoothing", 0.0)),
                    gradient_clip_norm=model.get("gradient_clip_norm"),
                    learning_rate_init=float(model.get("learning_rate_init", 0.001)),
                    learning_rate=str(model.get("learning_rate", "constant")),
                    min_learning_rate=float(model.get("min_learning_rate", 1e-6)),
                    warmup_steps=int(model.get("warmup_steps", 0)),
                    power_t=float(model.get("power_t", 0.5)),
                    momentum=float(model.get("momentum", 0.9)),
                    nesterovs_momentum=bool(model.get("nesterovs_momentum", True)),
                    beta_1=float(model.get("beta_1", 0.9)),
                    beta_2=float(model.get("beta_2", 0.999)),
                    epsilon=float(model.get("epsilon", 1e-8)),
                    tol=float(model.get("tol", 1e-4)),
                    max_iter=int(model.get("max_iter", 120)),
                    batch_size=model.get("batch_size", 64),
                    early_stopping=bool(model.get("early_stopping", True)),
                    validation_fraction=float(model.get("validation_fraction", 0.1)),
                    n_iter_no_change=int(model.get("n_iter_no_change", 10)),
                    shuffle=bool(model.get("shuffle", True)),
                    residual_connections=bool(model.get("residual_connections", False)),
                    loss=str(model.get("loss", "cross_entropy")),
                    focal_gamma=float(model.get("focal_gamma", 2.0)),
                    random_state=seed,
                )
            return libs["MLPClassifier"](
                hidden_layer_sizes=self._resolve_hidden_layer_sizes(model),
                activation=str(model.get("activation", "relu")),
                solver=str(model.get("solver", "adam")),
                alpha=float(model.get("weight_decay", model.get("alpha", 0.0005))),
                learning_rate_init=float(model.get("learning_rate_init", 0.001)),
                learning_rate=str(model.get("learning_rate", "constant")),
                power_t=float(model.get("power_t", 0.5)),
                momentum=float(model.get("momentum", 0.9)),
                nesterovs_momentum=bool(model.get("nesterovs_momentum", True)),
                beta_1=float(model.get("beta_1", 0.9)),
                beta_2=float(model.get("beta_2", 0.999)),
                epsilon=float(model.get("epsilon", 1e-8)),
                tol=float(model.get("tol", 1e-4)),
                max_iter=int(model.get("max_iter", 120)),
                batch_size=model.get("batch_size", 64),
                early_stopping=bool(model.get("early_stopping", True)),
                validation_fraction=float(model.get("validation_fraction", 0.1)),
                n_iter_no_change=int(model.get("n_iter_no_change", 10)),
                shuffle=bool(model.get("shuffle", True)),
                random_state=seed,
            )
        raise BackendError(f"Unsupported model family {candidate.model_family!r} for sklearn backend.")

    def _fit_estimator(
        self,
        estimator: Any,
        x_train: Any,
        y_train: list[Any],
        sample_weight: Any,
        candidate: CandidateConfig,
    ) -> None:
        if sample_weight is None:
            estimator.fit(x_train, y_train)
            return

        fit_signature = inspect.signature(estimator.fit)
        if "sample_weight" not in fit_signature.parameters:
            raise BackendError(
                f"Installed sklearn estimator for {candidate.model_family!r} does not expose "
                "fit(..., sample_weight=...). Use resampling instead or upgrade scikit-learn."
            )
        estimator.fit(x_train, y_train, sample_weight=sample_weight)

    def evaluate(
        self,
        benchmark: BenchmarkSpec,
        dataset: DatasetSpec,
        candidate: CandidateConfig,
    ) -> CandidateResult:
        if benchmark.metric != "accuracy":
            raise BackendError("The sklearn backend currently supports only accuracy.")

        libs = self._require_sklearn()
        features, labels, feature_kind = self._load_dataset(dataset, libs)
        x_train, x_val, x_test, y_train, y_val, y_test = self._split_dataset(
            features, labels, benchmark, libs
        )
        x_train, x_val, x_test = self._vectorize_features(
            dataset,
            feature_kind,
            x_train,
            x_val,
            x_test,
            libs,
        )
        x_train, x_val, x_test = self._apply_outlier_strategy(
            x_train, x_val, x_test, candidate.preprocessing, libs
        )
        x_train, x_val, x_test = self._apply_normalization(
            x_train, x_val, x_test, candidate.preprocessing, libs
        )
        x_train, x_val, x_test = self._apply_projection(
            x_train, x_val, x_test, candidate.preprocessing, libs
        )
        x_train, y_train = self._resample_training_data(
            x_train, y_train, candidate.resampling, benchmark.random_seed, libs
        )

        sample_weight = self._compute_sample_weight(
            y_train,
            candidate.model.get("class_weight"),
            libs,
        )
        estimator = self._make_estimator(libs, candidate, benchmark.random_seed)

        # MLP paths need numeric labels because sklearn's early-stopping score
        # checks call numpy predicates that reject string labels.
        if candidate.model_family == "mlp":
            label_encoder = libs["LabelEncoder"]()
            label_encoder.fit(list(y_train) + list(y_val) + list(y_test))
            y_train = label_encoder.transform(y_train).tolist()
            y_val = label_encoder.transform(y_val)
            y_test = label_encoder.transform(y_test)

        self._fit_estimator(estimator, x_train, y_train, sample_weight, candidate)

        accuracy_score = libs["accuracy_score"]
        validation_score = float(accuracy_score(y_val, estimator.predict(x_val)))
        test_score = float(accuracy_score(y_test, estimator.predict(x_test)))
        summary = (
            f"Measured {candidate.model_family} with normalization={candidate.preprocessing.get('normalization', 'none')}, "
            f"outlier={candidate.preprocessing.get('outlier_strategy', 'none')}, "
            f"resampling={candidate.resampling.get('strategy', 'none')}."
        )
        return CandidateResult(
            candidate_name=candidate.name,
            model_family=candidate.model_family,
            metric=benchmark.metric,
            validation_score=round(validation_score, 6),
            test_score=round(test_score, 6),
            rank=0,
            backend_name=self.backend_name,
            summary=summary,
            preprocessing=dict(candidate.preprocessing),
            resampling=dict(candidate.resampling),
            model=dict(candidate.model),
        )
