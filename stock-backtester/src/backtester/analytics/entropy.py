from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EntropyConfig:
    price_col: str = "close"
    return_col: str = "return"

    entropy_col: str = "entropy"
    normalized_entropy_col: str = "normalized_entropy"

    direction_col: str = "direction"
    direction_entropy_col: str = "direction_entropy"
    normalized_direction_entropy_col: str = "normalized_direction_entropy"

    entropy_window: int = 60
    zscore_window: int = 252
    n_bins: int = 10


def _shannon_entropy_from_probs(probs: np.ndarray) -> float:
    probs = probs[np.isfinite(probs)]
    probs = probs[probs > 0]

    if probs.size == 0:
        return np.nan

    return float(-(probs * np.log(probs)).sum())


def _shannon_entropy_binned(window: np.ndarray, n_bins: int) -> float:
    values = np.asarray(window, dtype=float)
    values = values[np.isfinite(values)]

    if values.size < 2:
        return np.nan

    counts, _ = np.histogram(values, bins=n_bins)
    total = counts.sum()

    if total == 0:
        return np.nan

    probs = counts[counts > 0] / total
    return _shannon_entropy_from_probs(probs)


def _directional_entropy(window: np.ndarray) -> float:
    values = np.asarray(window, dtype=float)
    values = values[np.isfinite(values)]

    if values.size < 2:
        return np.nan

    # Three states:
    # -1 = down day
    #  0 = flat day
    #  1 = up day
    states = np.sign(values)

    counts = np.array(
        [
            np.sum(states < 0),
            np.sum(states == 0),
            np.sum(states > 0),
        ],
        dtype=float,
    )

    total = counts.sum()

    if total == 0:
        return np.nan

    probs = counts[counts > 0] / total
    return _shannon_entropy_from_probs(probs)


def _rolling_percentile_of_last(window: np.ndarray) -> float:
    values = np.asarray(window, dtype=float)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return np.nan

    last = values[-1]
    return float((values <= last).sum() / values.size)


def _add_zscore_and_percentile(
    df: pd.DataFrame,
    value_col: str,
    zscore_col: str,
    percentile_col: str,
    window: int,
) -> pd.DataFrame:
    out = df.copy()

    rolling = out[value_col].rolling(
        window=window,
        min_periods=window,
    )

    mean = rolling.mean()
    std = rolling.std(ddof=0).replace(0, np.nan)

    out[zscore_col] = (out[value_col] - mean) / std

    out[percentile_col] = (
        out[value_col]
        .rolling(
            window=window,
            min_periods=window,
        )
        .apply(_rolling_percentile_of_last, raw=True)
    )

    return out


def compute_entropy_metrics(
    df: pd.DataFrame,
    config: EntropyConfig = EntropyConfig(),
) -> pd.DataFrame:
    if config.price_col not in df.columns:
        raise ValueError(f"Missing required price column: {config.price_col}")

    out = df.copy().sort_index()

    out[config.return_col] = out[config.price_col].pct_change()

    # ------------------------------------------------------------
    # 1. Return-distribution entropy
    # ------------------------------------------------------------
    out[config.entropy_col] = (
        out[config.return_col]
        .rolling(
            window=config.entropy_window,
            min_periods=config.entropy_window,
        )
        .apply(lambda x: _shannon_entropy_binned(x, config.n_bins), raw=True)
    )

    max_return_entropy = np.log(config.n_bins)

    out[config.normalized_entropy_col] = out[config.entropy_col] / max_return_entropy

    out = _add_zscore_and_percentile(
        out,
        value_col=config.normalized_entropy_col,
        zscore_col="entropy_zscore",
        percentile_col="entropy_percentile",
        window=config.zscore_window,
    )

    # ------------------------------------------------------------
    # 2. Directional entropy
    # ------------------------------------------------------------
    out[config.direction_col] = np.sign(out[config.return_col])

    out[config.direction_entropy_col] = (
        out[config.return_col]
        .rolling(
            window=config.entropy_window,
            min_periods=config.entropy_window,
        )
        .apply(_directional_entropy, raw=True)
    )

    # Max entropy for 3 direction states: down, flat, up.
    max_direction_entropy = np.log(3)

    out[config.normalized_direction_entropy_col] = (
        out[config.direction_entropy_col] / max_direction_entropy
    )

    out = _add_zscore_and_percentile(
        out,
        value_col=config.normalized_direction_entropy_col,
        zscore_col="direction_entropy_zscore",
        percentile_col="direction_entropy_percentile",
        window=config.zscore_window,
    )

    return out
