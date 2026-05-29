from __future__ import annotations

import numpy as np
import pandas as pd


def _rolling_percentile_of_last(window: np.ndarray) -> float:
    values = np.asarray(window, dtype=float)
    values = values[np.isfinite(values)]

    if values.size == 0:
        return np.nan

    last = values[-1]
    return float((values <= last).sum() / values.size)


def _classify_vol_regime(percentile: float) -> str:
    if pd.isna(percentile):
        return "UNKNOWN"

    if percentile < 0.25:
        return "LOW"

    if percentile < 0.75:
        return "NORMAL"

    if percentile < 0.95:
        return "HIGH"

    return "EXTREME"


def compute_fast_volatility_metrics(
    price_series: pd.DataFrame,
    price_col: str = "close",
    short_window: int = 21,
    long_window: int = 63,
    zscore_window: int = 252,
    spike_ratio: float = 1.75,
) -> pd.DataFrame:
    """
    Fast volatility proxy for broad universe scans and Monte Carlo.

    This avoids repeated GARCH fitting. It produces the same decision-facing
    fields expected by volatility_decision.py:

    - vol_regime
    - vol_zscore
    - vol_percentile
    - vol_spike_flag

    Use this for fast research loops. Keep GARCH for slower validation runs.
    """

    if price_col not in price_series.columns:
        raise ValueError(f"Missing required price column: {price_col}")

    out = price_series.copy().sort_index()

    close = out[price_col].astype(float)

    out["log_return"] = np.log(close).diff()

    out["fast_vol_short"] = out["log_return"].rolling(
        short_window, min_periods=short_window
    ).std(ddof=0) * np.sqrt(252)

    out["fast_vol"] = out["log_return"].rolling(
        long_window, min_periods=long_window
    ).std(ddof=0) * np.sqrt(252)

    rolling = out["fast_vol"].rolling(
        window=zscore_window,
        min_periods=zscore_window,
    )

    vol_mean = rolling.mean()
    vol_std = rolling.std(ddof=0).replace(0, np.nan)

    out["vol_zscore"] = (out["fast_vol"] - vol_mean) / vol_std

    out["vol_percentile"] = (
        out["fast_vol"]
        .rolling(
            window=zscore_window,
            min_periods=zscore_window,
        )
        .apply(_rolling_percentile_of_last, raw=True)
    )

    out["vol_spike_flag"] = out["fast_vol_short"] > (
        spike_ratio * out["fast_vol"].shift(1)
    )

    out["vol_regime"] = out["vol_percentile"].apply(_classify_vol_regime)

    return out
