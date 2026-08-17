from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration_dataset import feature_columns
from ..candidates import read_table


def standardize(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.nanmean(x, axis=0)
    std = np.nanstd(x, axis=0)
    std[std == 0] = 1.0
    return (x - mean) / std, mean, std


def prepare_training_frame(df: pd.DataFrame, features: list[str], target_col: str) -> tuple[pd.DataFrame, list[str], dict[str, float], list[str]]:
    """Keep target-valid rows and impute sparse feature columns.

    The intelligence/event feature matrix is intentionally sparse: not every
    ticker has every news/event feature on every run. Calibration should not
    discard the entire dataset because one feature is missing for one ticker.
    """
    if target_col not in df.columns:
        raise ValueError(f"Target column not found: {target_col}")

    usable = df.dropna(subset=[target_col]).copy()
    if usable.empty:
        raise ValueError(f"No usable training rows: target column {target_col!r} is all missing.")

    kept_features: list[str] = []
    impute_values: dict[str, float] = {}
    dropped_features: list[str] = []

    for feature in features:
        series = pd.to_numeric(usable[feature], errors="coerce")
        if series.notna().sum() == 0:
            dropped_features.append(feature)
            continue
        kept_features.append(feature)
        median = float(series.median())
        impute_values[feature] = 0.0 if np.isnan(median) else median
        usable[feature] = series.fillna(impute_values[feature])

    if not kept_features:
        raise ValueError("No usable numeric feature columns after dropping all-missing features.")

    return usable, kept_features, impute_values, dropped_features


def ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    xtx = x.T @ x
    penalty = alpha * np.eye(xtx.shape[0])
    return np.linalg.solve(xtx + penalty, x.T @ y)


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def logistic_fit(x: np.ndarray, y: np.ndarray, *, alpha: float = 1.0, lr: float = 0.05, steps: int = 1000) -> np.ndarray:
    beta = np.zeros(x.shape[1])
    for _ in range(steps):
        pred = sigmoid(x @ beta)
        grad = x.T @ (pred - y) / len(y) + alpha * beta / len(y)
        beta -= lr * grad
    return beta


def calibrate_weights(
    *,
    dataset_path: str | Path,
    target_col: str = "signal_success",
    out_json: str | Path,
    model_type: str = "logistic",
    alpha: float = 1.0,
) -> dict:
    df = read_table(dataset_path)
    features = feature_columns(df)
    usable, features, impute_values, dropped_features = prepare_training_frame(df, features, target_col)

    x_raw = usable[features].to_numpy(dtype=float)
    y = usable[target_col].to_numpy(dtype=float)
    x_std, mean, std = standardize(x_raw)
    x = np.column_stack([np.ones(len(x_std)), x_std])

    if model_type == "ridge":
        beta = ridge_fit(x, y, alpha=alpha)
        raw_score = x @ beta
        predictions = raw_score
    else:
        beta = logistic_fit(x, y, alpha=alpha)
        predictions = sigmoid(x @ beta)

    weights = {
        feature: float(coef)
        for feature, coef in sorted(zip(features, beta[1:]), key=lambda item: abs(item[1]), reverse=True)
    }
    result = {
        "model_type": model_type,
        "target_col": target_col,
        "rows": int(len(usable)),
        "features": features,
        "dropped_all_missing_features": dropped_features,
        "intercept": float(beta[0]),
        "weights": weights,
        "feature_mean": {feature: float(value) for feature, value in zip(features, mean)},
        "feature_std": {feature: float(value) for feature, value in zip(features, std)},
        "feature_impute_value": impute_values,
        "prediction_mean": float(np.nanmean(predictions)),
        "target_mean": float(np.nanmean(y)),
        "alpha": alpha,
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
