from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .candidates import read_table, write_table


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _as_numeric(series: pd.Series, fill_value: float) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(fill_value)


def calibrated_model_score(df: pd.DataFrame, calibration: dict) -> np.ndarray:
    features = list(calibration.get("features", []))
    weights = dict(calibration.get("weights", {}))
    means = dict(calibration.get("feature_mean", {}))
    stds = dict(calibration.get("feature_std", {}))
    imputes = dict(calibration.get("feature_impute_value", {}))
    intercept = float(calibration.get("intercept", 0.0))

    score = np.full(len(df), intercept, dtype=float)
    for feature in features:
        weight = float(weights.get(feature, 0.0))
        if weight == 0.0:
            continue
        mean = float(means.get(feature, 0.0))
        std = float(stds.get(feature, 1.0)) or 1.0
        fill = float(imputes.get(feature, mean))
        if feature in df.columns:
            values = _as_numeric(df[feature], fill).to_numpy(dtype=float)
        else:
            values = np.full(len(df), fill, dtype=float)
        z = (values - mean) / std
        score += weight * z
    return score


def normalize_score_to_multiplier(
    score: np.ndarray,
    *,
    model_type: str,
    min_multiplier: float = 0.70,
    max_multiplier: float = 1.15,
) -> tuple[np.ndarray, np.ndarray]:
    if model_type == "logistic":
        probability = sigmoid(score)
        centered = probability - np.nanmean(probability)
    else:
        centered = score - np.nanmean(score)
        scale = np.nanstd(centered)
        if scale and not np.isnan(scale):
            centered = centered / scale
        probability = sigmoid(centered)

    multiplier = 1.0 + 0.10 * centered
    multiplier = np.clip(multiplier, min_multiplier, max_multiplier)
    return probability, multiplier


def apply_calibrated_intelligence(
    *,
    signals_path: str | Path,
    calibration_json: str | Path,
    out_path: str | Path,
    baseline_confidence_col: str = "allocator_confidence_pre_intelligence",
    heuristic_confidence_col: str = "allocator_confidence_intelligence_adjusted",
    min_multiplier: float = 0.70,
    max_multiplier: float = 1.15,
) -> pd.DataFrame:
    df = read_table(signals_path).copy()
    calibration = json.loads(Path(calibration_json).read_text(encoding="utf-8"))
    if baseline_confidence_col not in df.columns:
        raise ValueError(f"Baseline confidence column not found: {baseline_confidence_col}")

    raw_score = calibrated_model_score(df, calibration)
    model_type = calibration.get("model_type", "ridge")
    probability, multiplier = normalize_score_to_multiplier(
        raw_score,
        model_type=model_type,
        min_multiplier=min_multiplier,
        max_multiplier=max_multiplier,
    )

    base = pd.to_numeric(df[baseline_confidence_col], errors="coerce").fillna(0.0)
    df["ml_intelligence_raw_score"] = raw_score
    df["ml_intelligence_probability"] = probability
    df["ml_intelligence_multiplier"] = multiplier
    df["allocator_confidence_ml_intelligence_adjusted"] = base * multiplier

    if heuristic_confidence_col in df.columns:
        heuristic = pd.to_numeric(df[heuristic_confidence_col], errors="coerce")
        df["ml_vs_heuristic_confidence_delta"] = df["allocator_confidence_ml_intelligence_adjusted"] - heuristic
    df["ml_vs_baseline_confidence_delta"] = df["allocator_confidence_ml_intelligence_adjusted"] - base

    write_table(df, out_path)
    return df
