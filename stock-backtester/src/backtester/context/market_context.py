# src/backtester/context/market_context.py

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def build_market_context_features(
    prices: pd.DataFrame,
    *,
    vol_window: int = 20,
    z_window: int = 120,
    entropy_window: int = 20,
    annualization: float = 252.0,
) -> pd.DataFrame:
    """
    Build date-level market context features.

    This is designed to become the shared context layer for:
        - mean reversion
        - volatility engines
        - entropy engines
        - allocator/risk logic

    Output:
        date
        market_return
        realized_vol
        realized_vol_z
        cross_sectional_dispersion
        return_entropy
        entropy_z
        volatility_weight
        entropy_weight
        context_weight
        volatility_state
        entropy_state
    """

    if prices.empty:
        raise ValueError("prices DataFrame is empty.")

    if vol_window < 2:
        raise ValueError("vol_window must be at least 2.")

    if z_window < 5:
        raise ValueError("z_window must be at least 5.")

    if entropy_window < 2:
        raise ValueError("entropy_window must be at least 2.")

    frame = prices.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    returns = frame.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    market_return = returns.mean(axis=1, skipna=True)

    realized_vol = market_return.rolling(
        vol_window, min_periods=max(5, vol_window // 2)
    ).std(ddof=1) * np.sqrt(annualization)

    realized_vol_z = rolling_zscore(realized_vol, z_window=z_window)

    cross_sectional_dispersion = returns.std(axis=1, skipna=True)

    daily_entropy = normalized_abs_return_entropy(returns)

    return_entropy = daily_entropy.rolling(
        entropy_window,
        min_periods=max(5, entropy_window // 2),
    ).mean()

    entropy_z = rolling_zscore(return_entropy, z_window=z_window)

    out = pd.DataFrame(
        {
            "date": frame.index,
            "market_return": market_return.to_numpy(dtype=np.float64),
            "realized_vol": realized_vol.to_numpy(dtype=np.float64),
            "realized_vol_z": realized_vol_z.to_numpy(dtype=np.float64),
            "cross_sectional_dispersion": cross_sectional_dispersion.to_numpy(
                dtype=np.float64
            ),
            "return_entropy": return_entropy.to_numpy(dtype=np.float64),
            "entropy_z": entropy_z.to_numpy(dtype=np.float64),
        }
    )

    out["volatility_state"] = classify_volatility_state(out["realized_vol_z"])
    out["entropy_state"] = classify_entropy_state(out["entropy_z"])

    out["volatility_weight"] = volatility_weight(out["realized_vol_z"])
    out["entropy_weight"] = entropy_weight(out["entropy_z"])

    out["context_weight"] = (out["volatility_weight"] * out["entropy_weight"]).clip(
        lower=0.0, upper=1.0
    )

    return out


def rolling_zscore(series: pd.Series, *, z_window: int) -> pd.Series:
    mean = series.rolling(z_window, min_periods=max(20, z_window // 4)).mean()
    std = series.rolling(z_window, min_periods=max(20, z_window // 4)).std(ddof=1)

    return (series - mean) / std.replace(0.0, np.nan)


def normalized_abs_return_entropy(returns: pd.DataFrame) -> pd.Series:
    """
    Compute normalized Shannon entropy of absolute stock returns per date.

    Interpretation:
        high entropy:
            movement is spread broadly across many names

        low entropy:
            movement is concentrated in fewer names

    This is not the final entropy engine, but it gives us a useful first
    market-structure context feature.
    """

    abs_returns = returns.abs()
    total_abs = abs_returns.sum(axis=1, skipna=True)

    probs = abs_returns.div(total_abs.replace(0.0, np.nan), axis=0)

    log_probs = np.log(probs.replace(0.0, np.nan))
    entropy = -(probs * log_probs).sum(axis=1, skipna=True)

    valid_counts = returns.notna().sum(axis=1)
    max_entropy = np.log(valid_counts.replace(0, np.nan))

    normalized = entropy / max_entropy.replace(0.0, np.nan)

    return normalized.clip(lower=0.0, upper=1.0)


def classify_volatility_state(vol_z: pd.Series) -> pd.Series:
    states = np.full(len(vol_z), "unknown", dtype=object)

    values = vol_z.to_numpy()

    states[values <= 0.5] = "normal"
    states[(values > 0.5) & (values <= 1.5)] = "elevated"
    states[values > 1.5] = "stress"
    states[pd.isna(values)] = "unknown"

    return pd.Series(states, index=vol_z.index)


def classify_entropy_state(entropy_z: pd.Series) -> pd.Series:
    states = np.full(len(entropy_z), "unknown", dtype=object)

    values = entropy_z.to_numpy()

    states[values <= -1.0] = "concentrated"
    states[(values > -1.0) & (values <= 1.0)] = "normal"
    states[values > 1.0] = "broad"
    states[pd.isna(values)] = "unknown"

    return pd.Series(states, index=entropy_z.index)


def volatility_weight(vol_z: pd.Series) -> pd.Series:
    """
    Weight for mean reversion.

    Philosophy:
        normal volatility: mean reversion can be trusted more
        elevated volatility: reduce confidence
        stress volatility: heavily reduce confidence
    """

    values = vol_z.to_numpy()
    weights = np.full(len(values), 1.0, dtype=np.float64)

    weights[(values > 0.5) & (values <= 1.5)] = 0.70
    weights[values > 1.5] = 0.35
    weights[pd.isna(values)] = 0.75

    return pd.Series(weights, index=vol_z.index)


def entropy_weight(entropy_z: pd.Series) -> pd.Series:
    """
    Weight for mean reversion.

    For now:
        normal entropy gets full weight
        very broad/high entropy gets reduced weight
        very concentrated entropy gets slightly reduced weight

    Later we can tune this based on actual forward-return evaluation.
    """

    values = entropy_z.to_numpy()
    weights = np.full(len(values), 1.0, dtype=np.float64)

    weights[values <= -1.0] = 0.85
    weights[values > 1.0] = 0.75
    weights[pd.isna(values)] = 0.75

    return pd.Series(weights, index=entropy_z.index)
