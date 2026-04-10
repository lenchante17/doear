from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))


def _activation_forward(name: str, values: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    if name == "identity":
        return values
    if name == "relu":
        return np.maximum(values, 0.0)
    if name == "leaky_relu":
        return np.where(values > 0.0, values, alpha * values)
    if name == "elu":
        return np.where(values > 0.0, values, alpha * (np.exp(np.clip(values, -40.0, 20.0)) - 1.0))
    if name == "softplus":
        positive = values > 0.0
        return np.where(positive, values + np.log1p(np.exp(-values)), np.log1p(np.exp(values)))
    if name == "gelu":
        cubic = values + 0.044715 * np.power(values, 3)
        return 0.5 * values * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * cubic))
    if name == "selu":
        selu_alpha = 1.6732632423543772
        selu_scale = 1.0507009873554805
        return selu_scale * np.where(values > 0.0, values, selu_alpha * (np.exp(np.clip(values, -40.0, 20.0)) - 1.0))
    if name == "tanh":
        return np.tanh(values)
    if name == "logistic":
        return _sigmoid(values)
    raise ValueError(f"Unsupported activation {name!r}.")


def _activation_backward(
    name: str,
    linear: np.ndarray,
    activated: np.ndarray,
    upstream: np.ndarray,
    alpha: float = 0.01,
) -> np.ndarray:
    if name == "identity":
        return upstream
    if name == "relu":
        return upstream * (activated > 0.0)
    if name == "leaky_relu":
        return upstream * np.where(linear > 0.0, 1.0, alpha)
    if name == "elu":
        derivative = np.where(linear > 0.0, 1.0, activated + alpha)
        return upstream * derivative
    if name == "softplus":
        return upstream * _sigmoid(linear)
    if name == "gelu":
        cubic = linear + 0.044715 * np.power(linear, 3)
        tanh_term = np.tanh(math.sqrt(2.0 / math.pi) * cubic)
        sech2 = 1.0 - np.square(tanh_term)
        slope = math.sqrt(2.0 / math.pi) * (1.0 + 3.0 * 0.044715 * np.square(linear))
        derivative = 0.5 * (1.0 + tanh_term) + 0.5 * linear * sech2 * slope
        return upstream * derivative
    if name == "selu":
        selu_alpha = 1.6732632423543772
        selu_scale = 1.0507009873554805
        derivative = selu_scale * np.where(linear > 0.0, 1.0, selu_alpha * np.exp(np.clip(linear, -40.0, 20.0)))
        return upstream * derivative
    if name == "tanh":
        return upstream * (1.0 - np.square(activated))
    if name == "logistic":
        return upstream * activated * (1.0 - activated)
    raise ValueError(f"Unsupported activation {name!r}.")


@dataclass
class _NormCache:
    normalized: np.ndarray
    centered: np.ndarray
    inverse_std: np.ndarray
    axis_size: int


class RepoMLPClassifier:
    """Small repo-native MLP used when the search space exceeds sklearn MLPClassifier."""

    def __init__(
        self,
        *,
        hidden_layer_sizes: tuple[int, ...],
        activation: str = "relu",
        activation_alpha: float = 0.01,
        weight_init: str = "auto",
        use_bias: bool = True,
        input_noise_std: float = 0.0,
        hidden_noise_std: float = 0.0,
        solver: str = "adam",
        alpha: float = 0.0005,
        weight_decay: float | None = None,
        bias_weight_decay: float = 0.0,
        normalization_weight_decay: float = 0.0,
        normalization_layer: str = "none",
        normalization_epsilon: float = 1e-5,
        normalization_momentum: float = 0.1,
        dropout_rate: float = 0.0,
        input_dropout_rate: float = 0.0,
        label_smoothing: float = 0.0,
        gradient_clip_norm: float | None = None,
        learning_rate_init: float = 0.001,
        learning_rate: str = "constant",
        min_learning_rate: float = 1e-6,
        warmup_steps: int = 0,
        power_t: float = 0.5,
        momentum: float = 0.9,
        nesterovs_momentum: bool = True,
        beta_1: float = 0.9,
        beta_2: float = 0.999,
        epsilon: float = 1e-8,
        tol: float = 1e-4,
        max_iter: int = 200,
        batch_size: int | str = 32,
        early_stopping: bool = False,
        validation_fraction: float = 0.1,
        n_iter_no_change: int = 10,
        shuffle: bool = True,
        residual_connections: bool = False,
        loss: str = "cross_entropy",
        focal_gamma: float = 2.0,
        random_state: int = 42,
    ) -> None:
        self.hidden_layer_sizes = tuple(int(item) for item in hidden_layer_sizes)
        self.activation = activation
        self.activation_alpha = float(activation_alpha)
        self.weight_init = weight_init
        self.use_bias = bool(use_bias)
        self.input_noise_std = float(input_noise_std)
        self.hidden_noise_std = float(hidden_noise_std)
        self.solver = solver
        self.alpha = float(alpha)
        self.weight_decay = float(weight_decay) if weight_decay is not None else None
        self.bias_weight_decay = float(bias_weight_decay)
        self.normalization_weight_decay = float(normalization_weight_decay)
        self.normalization_layer = normalization_layer
        self.normalization_epsilon = float(normalization_epsilon)
        self.normalization_momentum = float(normalization_momentum)
        self.dropout_rate = float(dropout_rate)
        self.input_dropout_rate = float(input_dropout_rate)
        self.label_smoothing = float(label_smoothing)
        self.gradient_clip_norm = float(gradient_clip_norm) if gradient_clip_norm is not None else None
        self.learning_rate_init = float(learning_rate_init)
        self.learning_rate = learning_rate
        self.min_learning_rate = float(min_learning_rate)
        self.warmup_steps = int(warmup_steps)
        self.power_t = float(power_t)
        self.momentum = float(momentum)
        self.nesterovs_momentum = bool(nesterovs_momentum)
        self.beta_1 = float(beta_1)
        self.beta_2 = float(beta_2)
        self.epsilon = float(epsilon)
        self.tol = float(tol)
        self.max_iter = int(max_iter)
        self.batch_size = batch_size
        self.early_stopping = bool(early_stopping)
        self.validation_fraction = float(validation_fraction)
        self.n_iter_no_change = int(n_iter_no_change)
        self.shuffle = bool(shuffle)
        self.residual_connections = bool(residual_connections)
        self.loss = loss
        self.focal_gamma = float(focal_gamma)
        self.random_state = int(random_state)

        self.classes_: np.ndarray | None = None
        self.weights_: list[np.ndarray] = []
        self.biases_: list[np.ndarray] = []
        self.norm_gammas_: list[np.ndarray] = []
        self.norm_betas_: list[np.ndarray] = []
        self.norm_running_means_: list[np.ndarray] = []
        self.norm_running_vars_: list[np.ndarray] = []
        self._adam_m: dict[str, list[np.ndarray]] = {}
        self._adam_v: dict[str, list[np.ndarray]] = {}
        self._rmsprop_avg: dict[str, list[np.ndarray]] = {}
        self._sgd_velocity: dict[str, list[np.ndarray]] = {}
        self._iteration_count = 0
        self._total_steps = 1
        self._rng: np.random.Generator | None = None

    def _uses_custom_norm(self) -> bool:
        return self.normalization_layer in {"layernorm", "batchnorm"}

    def _weight_decay_value(self) -> float:
        return self.weight_decay if self.weight_decay is not None else self.alpha

    def _batch_size_value(self, sample_count: int) -> int:
        if self.batch_size == "auto":
            return max(1, min(200, sample_count))
        return max(1, min(int(self.batch_size), sample_count))

    def _weight_scale(self, fan_in: int, fan_out: int, hidden_layer: bool) -> tuple[str, float]:
        init_mode = self.weight_init
        if init_mode == "auto":
            if hidden_layer and self.activation in {"relu", "leaky_relu", "elu"}:
                return "normal", math.sqrt(2.0 / fan_in)
            if hidden_layer and self.activation == "tanh":
                return "normal", math.sqrt(1.0 / fan_in)
            return "normal", math.sqrt(1.0 / max(1.0, fan_in))
        if init_mode == "xavier_uniform":
            return "uniform", math.sqrt(6.0 / (fan_in + fan_out))
        if init_mode == "xavier_normal":
            return "normal", math.sqrt(2.0 / (fan_in + fan_out))
        if init_mode == "he_uniform":
            return "uniform", math.sqrt(6.0 / fan_in)
        if init_mode == "he_normal":
            return "normal", math.sqrt(2.0 / fan_in)
        if init_mode == "lecun_uniform":
            return "uniform", math.sqrt(3.0 / fan_in)
        if init_mode == "lecun_normal":
            return "normal", math.sqrt(1.0 / fan_in)
        raise ValueError(f"Unsupported weight_init {init_mode!r}.")

    def _initialize_parameters(self, input_dim: int, output_dim: int, rng: np.random.Generator) -> None:
        layer_sizes = [input_dim, *self.hidden_layer_sizes, output_dim]
        self.weights_ = []
        self.biases_ = []
        self.norm_gammas_ = []
        self.norm_betas_ = []
        self.norm_running_means_ = []
        self.norm_running_vars_ = []

        for layer_index, (fan_in, fan_out) in enumerate(zip(layer_sizes[:-1], layer_sizes[1:])):
            distribution, scale = self._weight_scale(
                fan_in,
                fan_out,
                hidden_layer=layer_index < len(self.hidden_layer_sizes),
            )
            if distribution == "uniform":
                weight = rng.uniform(-scale, scale, size=(fan_in, fan_out))
            else:
                weight = rng.normal(0.0, scale, size=(fan_in, fan_out))
            self.weights_.append(weight.astype(np.float32))
            self.biases_.append(np.zeros(fan_out, dtype=np.float32))
            if layer_index < len(self.hidden_layer_sizes) and self._uses_custom_norm():
                self.norm_gammas_.append(np.ones(fan_out, dtype=np.float32))
                self.norm_betas_.append(np.zeros(fan_out, dtype=np.float32))
                self.norm_running_means_.append(np.zeros(fan_out, dtype=np.float32))
                self.norm_running_vars_.append(np.ones(fan_out, dtype=np.float32))

        def _zeros_like_group(values: list[np.ndarray]) -> list[np.ndarray]:
            return [np.zeros_like(item) for item in values]

        self._adam_m = {
            "weights": _zeros_like_group(self.weights_),
            "biases": _zeros_like_group(self.biases_),
            "gammas": _zeros_like_group(self.norm_gammas_),
            "betas": _zeros_like_group(self.norm_betas_),
        }
        self._adam_v = {
            "weights": _zeros_like_group(self.weights_),
            "biases": _zeros_like_group(self.biases_),
            "gammas": _zeros_like_group(self.norm_gammas_),
            "betas": _zeros_like_group(self.norm_betas_),
        }
        self._rmsprop_avg = {
            "weights": _zeros_like_group(self.weights_),
            "biases": _zeros_like_group(self.biases_),
            "gammas": _zeros_like_group(self.norm_gammas_),
            "betas": _zeros_like_group(self.norm_betas_),
        }
        self._sgd_velocity = {
            "weights": _zeros_like_group(self.weights_),
            "biases": _zeros_like_group(self.biases_),
            "gammas": _zeros_like_group(self.norm_gammas_),
            "betas": _zeros_like_group(self.norm_betas_),
        }

    def _current_learning_rate(self) -> float:
        step = max(1, self._iteration_count)
        learning_rate = self.learning_rate_init
        if self.learning_rate == "invscaling":
            learning_rate = self.learning_rate_init / (step**self.power_t)
        elif self.learning_rate == "cosine":
            progress = min(1.0, (step - 1) / max(1, self._total_steps))
            learning_rate = self.min_learning_rate + 0.5 * (self.learning_rate_init - self.min_learning_rate) * (
                1.0 + math.cos(math.pi * progress)
            )
        elif self.learning_rate == "linear_decay":
            progress = min(1.0, (step - 1) / max(1, self._total_steps))
            learning_rate = self.learning_rate_init + (
                self.min_learning_rate - self.learning_rate_init
            ) * progress

        if self.warmup_steps > 0 and step <= self.warmup_steps:
            warmup_progress = step / max(1, self.warmup_steps)
            learning_rate = self.min_learning_rate + (learning_rate - self.min_learning_rate) * warmup_progress

        return max(self.min_learning_rate, learning_rate)

    def _normalize_forward(
        self,
        values: np.ndarray,
        layer_index: int,
        *,
        training: bool,
    ) -> tuple[np.ndarray, _NormCache]:
        gamma = self.norm_gammas_[layer_index]
        beta = self.norm_betas_[layer_index]
        epsilon = self.normalization_epsilon

        if self.normalization_layer == "layernorm":
            mean = np.mean(values, axis=1, keepdims=True)
            variance = np.var(values, axis=1, keepdims=True)
            inverse_std = 1.0 / np.sqrt(variance + epsilon)
            centered = values - mean
            normalized = centered * inverse_std
            output = normalized * gamma + beta
            return output, _NormCache(
                normalized=normalized,
                centered=centered,
                inverse_std=inverse_std,
                axis_size=values.shape[1],
            )

        if self.normalization_layer == "batchnorm":
            if training:
                mean = np.mean(values, axis=0, keepdims=True)
                variance = np.var(values, axis=0, keepdims=True)
                self.norm_running_means_[layer_index] = (
                    (1.0 - self.normalization_momentum) * self.norm_running_means_[layer_index]
                    + self.normalization_momentum * mean.squeeze(0)
                )
                self.norm_running_vars_[layer_index] = (
                    (1.0 - self.normalization_momentum) * self.norm_running_vars_[layer_index]
                    + self.normalization_momentum * variance.squeeze(0)
                )
            else:
                mean = self.norm_running_means_[layer_index][None, :]
                variance = self.norm_running_vars_[layer_index][None, :]
            inverse_std = 1.0 / np.sqrt(variance + epsilon)
            centered = values - mean
            normalized = centered * inverse_std
            output = normalized * gamma + beta
            return output, _NormCache(
                normalized=normalized,
                centered=centered,
                inverse_std=inverse_std,
                axis_size=values.shape[0],
            )

        raise ValueError(f"Unsupported normalization layer {self.normalization_layer!r}.")

    def _normalize_backward(
        self,
        upstream: np.ndarray,
        cache: _NormCache,
        layer_index: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        gamma = self.norm_gammas_[layer_index]
        dgamma = np.sum(upstream * cache.normalized, axis=0)
        dbeta = np.sum(upstream, axis=0)
        dxhat = upstream * gamma

        if self.normalization_layer == "layernorm":
            axis = 1
        elif self.normalization_layer == "batchnorm":
            axis = 0
        else:
            raise ValueError(f"Unsupported normalization layer {self.normalization_layer!r}.")

        dvar = np.sum(dxhat * cache.centered * -0.5 * np.power(cache.inverse_std, 3), axis=axis, keepdims=True)
        dmean = np.sum(-dxhat * cache.inverse_std, axis=axis, keepdims=True)
        dmean += dvar * np.mean(-2.0 * cache.centered, axis=axis, keepdims=True)
        dx = dxhat * cache.inverse_std
        dx += dvar * 2.0 * cache.centered / cache.axis_size
        dx += dmean / cache.axis_size
        return dx, dgamma, dbeta

    def _forward(
        self,
        X: np.ndarray,
        *,
        training: bool,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        activations = X
        if training and self.input_noise_std > 0.0:
            activations = activations + self._rng.normal(
                0.0,
                self.input_noise_std,
                size=activations.shape,
            ).astype(np.float32)
        if training and self.input_dropout_rate > 0.0:
            keep_prob = max(1e-6, 1.0 - self.input_dropout_rate)
            input_mask = (
                self._rng.random(activations.shape, dtype=np.float32) < keep_prob
            ).astype(np.float32) / keep_prob
            activations = activations * input_mask
        caches: list[dict[str, Any]] = []

        for layer_index in range(len(self.hidden_layer_sizes)):
            residual_source = activations
            linear = activations @ self.weights_[layer_index]
            if self.use_bias:
                linear = linear + self.biases_[layer_index]
            norm_cache = None
            if self._uses_custom_norm():
                linear, norm_cache = self._normalize_forward(linear, layer_index, training=training)
            activated = _activation_forward(self.activation, linear, self.activation_alpha)
            activation_output = activated
            if training and self.hidden_noise_std > 0.0:
                activated = activated + self._rng.normal(
                    0.0,
                    self.hidden_noise_std,
                    size=activated.shape,
                ).astype(np.float32)
            dropout_mask = None
            if training and self.dropout_rate > 0.0:
                keep_prob = max(1e-6, 1.0 - self.dropout_rate)
                dropout_mask = (
                    self._rng.random(activated.shape, dtype=np.float32) < keep_prob
                ).astype(np.float32) / keep_prob
                activated = activated * dropout_mask
            residual_added = False
            if self.residual_connections and residual_source.shape[1] == activated.shape[1]:
                activated = activated + residual_source
                residual_added = True
            caches.append(
                {
                    "inputs": activations,
                    "linear": linear,
                    "activated": activated,
                    "activation_output": activation_output,
                    "norm_cache": norm_cache,
                    "dropout_mask": dropout_mask,
                    "residual_added": residual_added,
                }
            )
            activations = activated

        logits = activations @ self.weights_[-1]
        if self.use_bias:
            logits = logits + self.biases_[-1]
        caches.append({"inputs": activations, "logits": logits})
        return logits, caches

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        shifted = logits - np.max(logits, axis=1, keepdims=True)
        exp_values = np.exp(shifted)
        return exp_values / np.sum(exp_values, axis=1, keepdims=True)

    def _loss_and_gradients(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: np.ndarray | None,
    ) -> tuple[float, dict[str, list[np.ndarray]]]:
        logits, caches = self._forward(X, training=True)
        probabilities = self._softmax(logits)
        one_hot = np.eye(probabilities.shape[1], dtype=np.float32)[y]
        if self.label_smoothing > 0.0:
            one_hot = (1.0 - self.label_smoothing) * one_hot + self.label_smoothing / probabilities.shape[1]

        if sample_weight is None:
            weights = np.ones((X.shape[0], 1), dtype=np.float32)
        else:
            weights = sample_weight.reshape(-1, 1).astype(np.float32)
        normalizer = float(np.sum(weights))
        clipped_probabilities = np.clip(probabilities, 1e-8, 1.0)
        if self.loss == "focal":
            pt = np.sum(one_hot * clipped_probabilities, axis=1, keepdims=True)
            focal_factor = np.power(1.0 - pt, self.focal_gamma)
            loss = -np.sum(weights * focal_factor * one_hot * np.log(clipped_probabilities)) / normalizer
            delta = focal_factor * (probabilities - one_hot) * (weights / normalizer)
        else:
            loss = -np.sum(weights * one_hot * np.log(clipped_probabilities)) / normalizer
            delta = (probabilities - one_hot) * (weights / normalizer)

        grads = {
            "weights": [np.zeros_like(item) for item in self.weights_],
            "biases": [np.zeros_like(item) for item in self.biases_],
            "gammas": [np.zeros_like(item) for item in self.norm_gammas_],
            "betas": [np.zeros_like(item) for item in self.norm_betas_],
        }

        decay = self._weight_decay_value()
        gradient_decay = 0.0 if self.solver == "adamw" else decay
        for weight in self.weights_:
            loss += 0.5 * decay * float(np.sum(np.square(weight)))
        if self.use_bias:
            for bias in self.biases_:
                loss += 0.5 * self.bias_weight_decay * float(np.sum(np.square(bias)))
        for gamma in self.norm_gammas_:
            loss += 0.5 * self.normalization_weight_decay * float(np.sum(np.square(gamma)))
        for beta in self.norm_betas_:
            loss += 0.5 * self.normalization_weight_decay * float(np.sum(np.square(beta)))

        output_cache = caches[-1]
        grads["weights"][-1] = output_cache["inputs"].T @ delta + gradient_decay * self.weights_[-1]
        if self.use_bias:
            grads["biases"][-1] = np.sum(delta, axis=0) + self.bias_weight_decay * self.biases_[-1]
        delta = delta @ self.weights_[-1].T

        for layer_index in reversed(range(len(self.hidden_layer_sizes))):
            cache = caches[layer_index]
            residual_delta = delta if cache["residual_added"] else None
            if cache["dropout_mask"] is not None:
                delta = delta * cache["dropout_mask"]
            delta = _activation_backward(
                self.activation,
                cache["linear"],
                cache["activation_output"],
                delta,
                self.activation_alpha,
            )
            if self._uses_custom_norm():
                delta, dgamma, dbeta = self._normalize_backward(delta, cache["norm_cache"], layer_index)
                grads["gammas"][layer_index] = dgamma + self.normalization_weight_decay * self.norm_gammas_[layer_index]
                grads["betas"][layer_index] = dbeta + self.normalization_weight_decay * self.norm_betas_[layer_index]
            grads["weights"][layer_index] = cache["inputs"].T @ delta + gradient_decay * self.weights_[layer_index]
            if self.use_bias:
                grads["biases"][layer_index] = np.sum(delta, axis=0) + self.bias_weight_decay * self.biases_[layer_index]
            if layer_index > 0:
                delta = delta @ self.weights_[layer_index].T
                if residual_delta is not None:
                    delta = delta + residual_delta

        return float(loss), grads

    def _clip_gradients(self, gradients: dict[str, list[np.ndarray]]) -> dict[str, list[np.ndarray]]:
        if self.gradient_clip_norm is None:
            return gradients
        threshold = self.gradient_clip_norm
        for group in gradients.values():
            for index, grad in enumerate(group):
                grad_norm = float(np.linalg.norm(grad))
                if grad_norm > threshold and grad_norm > 0.0:
                    group[index] = grad * (threshold / grad_norm)
        return gradients

    def _apply_adam_update(self, group: str, index: int, gradients: np.ndarray) -> np.ndarray:
        learning_rate = self._current_learning_rate()
        self._adam_m[group][index] = self.beta_1 * self._adam_m[group][index] + (1.0 - self.beta_1) * gradients
        self._adam_v[group][index] = self.beta_2 * self._adam_v[group][index] + (1.0 - self.beta_2) * np.square(gradients)
        m_hat = self._adam_m[group][index] / (1.0 - self.beta_1**self._iteration_count)
        v_hat = self._adam_v[group][index] / (1.0 - self.beta_2**self._iteration_count)
        return -learning_rate * m_hat / (np.sqrt(v_hat) + self.epsilon)

    def _apply_sgd_update(self, group: str, index: int, gradients: np.ndarray) -> np.ndarray:
        lr = self._current_learning_rate()
        velocity = self.momentum * self._sgd_velocity[group][index] - lr * gradients
        if self.nesterovs_momentum:
            update = self.momentum * velocity - lr * gradients
        else:
            update = velocity
        self._sgd_velocity[group][index] = velocity
        return update

    def _apply_rmsprop_update(self, group: str, index: int, gradients: np.ndarray) -> np.ndarray:
        learning_rate = self._current_learning_rate()
        self._rmsprop_avg[group][index] = self.beta_2 * self._rmsprop_avg[group][index] + (1.0 - self.beta_2) * np.square(
            gradients
        )
        return -learning_rate * gradients / (np.sqrt(self._rmsprop_avg[group][index]) + self.epsilon)

    def _apply_gradients(self, gradients: dict[str, list[np.ndarray]]) -> None:
        self._iteration_count += 1
        for group, params in (
            ("weights", self.weights_),
            ("biases", self.biases_),
            ("gammas", self.norm_gammas_),
            ("betas", self.norm_betas_),
        ):
            for index, param in enumerate(params):
                grad = gradients[group][index]
                if self.solver == "adam":
                    update = self._apply_adam_update(group, index, grad)
                elif self.solver == "adamw":
                    update = self._apply_adam_update(group, index, grad)
                elif self.solver == "sgd":
                    update = self._apply_sgd_update(group, index, grad)
                elif self.solver == "rmsprop":
                    update = self._apply_rmsprop_update(group, index, grad)
                else:
                    raise ValueError(
                        "RepoMLPClassifier supports solver='adam', 'adamw', 'rmsprop', or 'sgd' when "
                        "internal normalization or extended weight decay is enabled."
                    )
                next_param = param + update.astype(np.float32)
                if self.solver == "adamw":
                    learning_rate = self._current_learning_rate()
                    if group == "weights":
                        decay = self._weight_decay_value()
                    elif group == "biases":
                        decay = self.bias_weight_decay
                    else:
                        decay = self.normalization_weight_decay
                    next_param = next_param - learning_rate * decay * param
                params[index] = next_param.astype(np.float32)

    def _score(self, X: np.ndarray, y: np.ndarray) -> float:
        predictions = self.predict(X)
        return float(np.mean(predictions == self.classes_[y]))

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None) -> "RepoMLPClassifier":
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y)
        self.classes_, y_indices = np.unique(y, return_inverse=True)
        rng = np.random.default_rng(self.random_state)
        self._rng = rng

        train_X = X
        train_y = y_indices
        train_weight = None if sample_weight is None else np.asarray(sample_weight, dtype=np.float32)
        val_X = None
        val_y = None

        if self.early_stopping and X.shape[0] >= 10:
            order = np.arange(X.shape[0])
            rng.shuffle(order)
            val_count = max(1, int(round(X.shape[0] * self.validation_fraction)))
            val_indices = order[:val_count]
            train_indices = order[val_count:]
            if train_indices.size > 0:
                val_X = X[val_indices]
                val_y = y_indices[val_indices]
                train_X = X[train_indices]
                train_y = y_indices[train_indices]
                if train_weight is not None:
                    val_weight = train_weight[val_indices]
                    train_weight = train_weight[train_indices]
                else:
                    val_weight = None
            else:
                val_weight = None
        else:
            val_weight = None

        self._initialize_parameters(train_X.shape[1], len(self.classes_), rng)
        best_snapshot = None
        best_score = -np.inf
        stagnant_epochs = 0
        batch_size = self._batch_size_value(train_X.shape[0])
        self._total_steps = max(1, math.ceil(train_X.shape[0] / batch_size) * self.max_iter)

        for _ in range(self.max_iter):
            order = np.arange(train_X.shape[0])
            if self.shuffle:
                rng.shuffle(order)
            for start in range(0, train_X.shape[0], batch_size):
                batch_indices = order[start : start + batch_size]
                batch_X = train_X[batch_indices]
                batch_y = train_y[batch_indices]
                batch_weight = None if train_weight is None else train_weight[batch_indices]
                _, gradients = self._loss_and_gradients(batch_X, batch_y, batch_weight)
                gradients = self._clip_gradients(gradients)
                self._apply_gradients(gradients)

            if val_X is not None and val_y is not None:
                score = self._score(val_X, val_y)
                if score > best_score + self.tol:
                    best_score = score
                    stagnant_epochs = 0
                    best_snapshot = (
                        [item.copy() for item in self.weights_],
                        [item.copy() for item in self.biases_],
                        [item.copy() for item in self.norm_gammas_],
                        [item.copy() for item in self.norm_betas_],
                        [item.copy() for item in self.norm_running_means_],
                        [item.copy() for item in self.norm_running_vars_],
                    )
                else:
                    stagnant_epochs += 1
                if stagnant_epochs >= self.n_iter_no_change:
                    break

        if best_snapshot is not None:
            (
                self.weights_,
                self.biases_,
                self.norm_gammas_,
                self.norm_betas_,
                self.norm_running_means_,
                self.norm_running_vars_,
            ) = best_snapshot

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        logits, _ = self._forward(X, training=False)
        predictions = np.argmax(logits, axis=1)
        return self.classes_[predictions]
