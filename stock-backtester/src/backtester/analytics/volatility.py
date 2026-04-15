from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:
    from arch import arch_model
except ImportError as exc:
    raise ImportError(
        "The 'arch' package is required for GARCH volatility metrics. "
        "Install it with: pip install arch"
    ) from exc


@dataclass(frozen=True)
class GarchConfig:
    p: int = 1
    q: int = 1
    returns_scale: float = 100.0
    annualization_factor: int = 252
    regime_window: int = 100
    percentile_window: int = 252
    shock_window: int = 20
    vol_of_vol_window: int = 20
    mean: str = "zero"
    dist: str = "normal"
    low_threshold: float = -1.0
    high_threshold: float = 1.5


# ---------------------------
# Data Validation
# ---------------------------


def _validate_price_series(price_series: pd.Series | pd.DataFrame) -> pd.Series:
    if isinstance(price_series, pd.DataFrame):
        if price_series.shape[1] == 1:
            price_series = price_series.squeeze()
        else:
            raise ValueError("price_series DataFrame must have exactly one column")

    if not isinstance(price_series, pd.Series):
        raise TypeError("price_series must be a pandas Series")

    cleaned = price_series.dropna().astype(float)

    if cleaned.empty:
        raise ValueError("price_series is empty after dropping NaN values")

    if (cleaned <= 0).any():
        raise ValueError("price_series must contain only positive values")

    if len(cleaned) < 50:
        raise ValueError(
            "price_series is too short for stable GARCH estimation; need at least 50 points"
        )

    return cleaned


# ---------------------------
# Core Calculations
# ---------------------------


def compute_log_returns(price_series: pd.Series) -> pd.Series:
    prices = _validate_price_series(price_series)
    returns = np.log(prices / prices.shift(1)).dropna()

    if returns.empty:
        raise ValueError("Not enough data to compute returns")

    returns.name = "log_return"
    return returns


def _rolling_percentile_rank(window_values: pd.Series) -> float:
    s = pd.Series(window_values)
    return float(s.rank(pct=True).iloc[-1])


def classify_vol_regime(
    z_score: pd.Series,
    low_threshold: float,
    high_threshold: float,
) -> pd.Series:
    regime = pd.Series(index=z_score.index, dtype="object")
    regime[:] = np.nan

    regime[z_score < low_threshold] = "LOW"
    regime[(z_score >= low_threshold) & (z_score <= high_threshold)] = "NORMAL"
    regime[z_score > high_threshold] = "HIGH"

    return regime


# ---------------------------
# GARCH Model
# ---------------------------


def fit_garch_volatility(
    returns: pd.Series,
    config: GarchConfig | None = None,
) -> pd.Series:
    cfg = config or GarchConfig()

    if returns.empty:
        raise ValueError("returns is empty")

    scaled_returns = returns * cfg.returns_scale

    model = arch_model(
        scaled_returns,
        vol="Garch",
        p=cfg.p,
        q=cfg.q,
        mean=cfg.mean,
        dist=cfg.dist,
        rescale=False,
    )

    try:
        result = model.fit(disp="off")
    except Exception as exc:
        raise RuntimeError(f"GARCH model fitting failed: {exc}") from exc

    vol = result.conditional_volatility / cfg.returns_scale
    vol = vol.reindex(returns.index)
    vol.name = "garch_vol"

    return vol


# ---------------------------
# Metrics Builder
# ---------------------------


def compute_garch_metrics(
    price_series: pd.Series,
    config: GarchConfig | None = None,
) -> pd.DataFrame:
    cfg = config or GarchConfig()

    returns = compute_log_returns(price_series)
    garch_vol = fit_garch_volatility(returns, config=cfg)

    df = pd.DataFrame(index=returns.index)

    # Returns + shocks
    df["log_return"] = returns
    df["abs_return"] = returns.abs()
    df["shock"] = returns.pow(2)
    df["shock_ma"] = df["shock"].rolling(cfg.shock_window).mean()

    # Volatility
    df["garch_vol"] = garch_vol
    df["garch_var"] = garch_vol.pow(2)
    df["garch_vol_annualized"] = garch_vol * np.sqrt(cfg.annualization_factor)

    # Changes
    df["vol_change"] = garch_vol.diff()

    safe_prev_vol = garch_vol.shift(1).replace(0, np.nan)
    df["vol_change_pct"] = df["vol_change"] / safe_prev_vol
    df["vol_change_pct"] = df["vol_change_pct"].replace([np.inf, -np.inf], np.nan)

    # Volatility trend
    df["vol_trend"] = garch_vol.rolling(5).mean().diff()

    # Z-score
    rolling_mean = garch_vol.rolling(cfg.regime_window).mean()
    rolling_std = garch_vol.rolling(cfg.regime_window).std()
    df["vol_zscore"] = (garch_vol - rolling_mean) / rolling_std

    # Percentile
    df["vol_percentile"] = garch_vol.rolling(cfg.percentile_window).apply(
        _rolling_percentile_rank,
        raw=False,
    )

    # Vol of vol
    df["vol_of_vol"] = garch_vol.rolling(cfg.vol_of_vol_window).std()

    # Regime
    df["vol_regime"] = classify_vol_regime(
        df["vol_zscore"],
        cfg.low_threshold,
        cfg.high_threshold,
    )

    # Flags
    df["vol_spike_flag"] = (
        (df["vol_change_pct"] > 0.10)
        & (df["vol_zscore"] > cfg.high_threshold)
        & (df["vol_percentile"] > 0.7)
    )

    df["vol_high_flag"] = df["vol_percentile"] > 0.80

    return df


# ---------------------------
# Snapshot
# ---------------------------


def latest_garch_snapshot(
    price_series: pd.Series,
    config: GarchConfig | None = None,
) -> dict[str, Any]:
    metrics = compute_garch_metrics(price_series, config=config)
    latest = metrics.iloc[-1]

    return {
        "date": metrics.index[-1],
        "garch_vol": float(latest["garch_vol"]),
        "garch_vol_annualized": float(latest["garch_vol_annualized"]),
        "vol_change": (
            float(latest["vol_change"]) if pd.notna(latest["vol_change"]) else np.nan
        ),
        "vol_change_pct": (
            float(latest["vol_change_pct"])
            if pd.notna(latest["vol_change_pct"])
            else np.nan
        ),
        "vol_zscore": (
            float(latest["vol_zscore"]) if pd.notna(latest["vol_zscore"]) else np.nan
        ),
        "vol_percentile": (
            float(latest["vol_percentile"])
            if pd.notna(latest["vol_percentile"])
            else np.nan
        ),
        "vol_of_vol": (
            float(latest["vol_of_vol"]) if pd.notna(latest["vol_of_vol"]) else np.nan
        ),
        "vol_regime": latest["vol_regime"],
        "vol_spike_flag": (
            bool(latest["vol_spike_flag"])
            if pd.notna(latest["vol_spike_flag"])
            else False
        ),
        "vol_high_flag": (
            bool(latest["vol_high_flag"])
            if pd.notna(latest["vol_high_flag"])
            else False
        ),
    }
