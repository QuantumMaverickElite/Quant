# src/backtester/correlation/regime.py

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from backtester.correlation.features import to_numpy, window_corr_matrix
from backtester.correlation.types import ReturnMatrix


@dataclass(frozen=True)
class RegimeCorrelationConfig:
    window: int = 120
    step: int = 5
    backend: str = "numpy"
    regime_column: str = "volatility_state"
    calm_regimes: tuple[str, ...] = ("LOW", "NORMAL", "CALM")
    stress_regimes: tuple[str, ...] = ("HIGH", "EXTREME", "ELEVATED", "STRESS")
    min_obs_per_regime: int = 5


def _get_array_module(backend: str) -> Any:
    backend = backend.lower().strip()

    if backend == "numpy":
        return np

    if backend == "cupy":
        try:
            import cupy as cp

            return cp
        except ImportError as exc:
            raise ImportError(
                "CuPy backend requested but cupy is not installed."
            ) from exc

    raise ValueError(f"Unsupported backend: {backend}")


def _upper_triangle_pair_frame(
    corr: np.ndarray,
    tickers: list[str],
    *,
    date: pd.Timestamp,
    window: int,
    regime: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for i, j in combinations(range(len(tickers)), 2):
        rows.append(
            {
                "date": date,
                "window": window,
                "regime": regime,
                "ticker_a": tickers[i],
                "ticker_b": tickers[j],
                "corr": float(corr[i, j]),
            }
        )

    return pd.DataFrame(rows)


def compute_rolling_regime_pair_correlations(
    return_matrix: ReturnMatrix,
    market_context: pd.DataFrame,
    config: RegimeCorrelationConfig,
) -> pd.DataFrame:
    """
    Compute rolling pairwise correlations and attach the market regime
    observed on the window end date.

    Output is pair-level:
        date, window, regime, ticker_a, ticker_b, corr
    """

    return_matrix.validate()

    if config.window < 2:
        raise ValueError("window must be at least 2.")

    if config.step < 1:
        raise ValueError("step must be positive.")

    context = market_context.copy()
    context["date"] = pd.to_datetime(context["date"])
    context = context.sort_values("date")

    if config.regime_column not in context.columns:
        raise ValueError(
            f"regime_column={config.regime_column!r} not found in market_context."
        )

    regime_by_date = (
        context[["date", config.regime_column]]
        .drop_duplicates("date")
        .set_index("date")[config.regime_column]
    )

    xp = _get_array_module(config.backend)

    values = xp.asarray(return_matrix.values)
    dates = pd.DatetimeIndex(return_matrix.dates)
    tickers = list(return_matrix.tickers)

    frames: list[pd.DataFrame] = []

    for end_idx in range(config.window - 1, len(dates), config.step):
        date = pd.Timestamp(dates[end_idx])

        if date not in regime_by_date.index:
            continue

        regime = regime_by_date.loc[date]

        if pd.isna(regime):
            continue

        start_idx = end_idx - config.window + 1
        window_values = values[start_idx : end_idx + 1, :]

        corr = window_corr_matrix(window_values, xp=xp)
        corr_np = to_numpy(corr).astype(np.float32, copy=False)

        frames.append(
            _upper_triangle_pair_frame(
                corr_np,
                tickers,
                date=date,
                window=config.window,
                regime=str(regime),
            )
        )

    if not frames:
        return pd.DataFrame(
            columns=["date", "window", "regime", "ticker_a", "ticker_b", "corr"]
        )

    return pd.concat(frames, ignore_index=True)


def summarize_regime_pair_correlations(
    pair_correlations: pd.DataFrame,
    config: RegimeCorrelationConfig,
) -> pd.DataFrame:
    """
    Collapse rolling pair correlations into calm/stress summaries.

    Output:
        ticker_a, ticker_b, calm_corr, stress_corr, stress_corr_delta, etc.
    """

    if pair_correlations.empty:
        return pd.DataFrame()

    df = pair_correlations.copy()
    df["regime"] = df["regime"].astype(str)
    df["regime"] = df["regime"].str.upper().str.strip()

    df["regime_bucket"] = np.select(
        [
            df["regime"].isin(config.calm_regimes),
            df["regime"].isin(config.stress_regimes),
        ],
        ["calm", "stress"],
        default="other",
    )

    df = df[df["regime_bucket"].isin(["calm", "stress"])].copy()

    grouped = df.groupby(["ticker_a", "ticker_b", "regime_bucket"], as_index=False).agg(
        avg_corr=("corr", "mean"),
        median_corr=("corr", "median"),
        obs=("corr", "size"),
    )

    wide = grouped.pivot(
        index=["ticker_a", "ticker_b"],
        columns="regime_bucket",
        values=["avg_corr", "median_corr", "obs"],
    )

    wide.columns = [f"{metric}_{bucket}" for metric, bucket in wide.columns]
    wide = wide.reset_index()

    for col in [
        "avg_corr_calm",
        "avg_corr_stress",
        "median_corr_calm",
        "median_corr_stress",
        "obs_calm",
        "obs_stress",
    ]:
        if col not in wide.columns:
            wide[col] = np.nan

    wide = wide[
        (wide["obs_calm"].fillna(0) >= config.min_obs_per_regime)
        & (wide["obs_stress"].fillna(0) >= config.min_obs_per_regime)
    ].copy()

    wide["stress_corr_delta"] = wide["avg_corr_stress"] - wide["avg_corr_calm"]
    wide["stress_corr_ratio"] = wide["avg_corr_stress"] / wide["avg_corr_calm"].replace(
        0, np.nan
    )
    wide["abs_stress_corr_delta"] = wide["stress_corr_delta"].abs()
    delta_mean = wide["stress_corr_delta"].mean()
    delta_std = wide["stress_corr_delta"].std(ddof=0)

    if delta_std and np.isfinite(delta_std):
        wide["stress_corr_delta_z"] = (
            wide["stress_corr_delta"] - delta_mean
        ) / delta_std
    else:
        wide["stress_corr_delta_z"] = 0.0

    wide["diversification_failure_label"] = np.select(
        [
            wide["stress_corr_delta"] >= 0.05,
            wide["stress_corr_delta"] >= 0.025,
            wide["stress_corr_delta"] <= -0.05,
            wide["stress_corr_delta"] <= -0.025,
        ],
        [
            "MAJOR_COMPRESSION",
            "MODERATE_COMPRESSION",
            "MAJOR_FRAGMENTATION",
            "MODERATE_FRAGMENTATION",
        ],
        default="STABLE",
    )

    wide = wide.sort_values(
        ["stress_corr_delta", "avg_corr_stress"],
        ascending=[False, False],
    ).reset_index(drop=True)

    wide["compression_rank"] = np.arange(1, len(wide) + 1)
    wide["fragmentation_rank"] = (
        wide["stress_corr_delta"].rank(method="first", ascending=True).astype(int)
    )

    return wide


def summarize_ticker_stress_sensitivity(summary: pd.DataFrame) -> pd.DataFrame:
    """
    Convert pair-level stress deltas into ticker-level stress sensitivity.
    """

    if summary.empty:
        return pd.DataFrame()

    left = summary.rename(columns={"ticker_a": "ticker"})[
        ["ticker", "stress_corr_delta", "avg_corr_calm", "avg_corr_stress"]
    ]
    right = summary.rename(columns={"ticker_b": "ticker"})[
        ["ticker", "stress_corr_delta", "avg_corr_calm", "avg_corr_stress"]
    ]

    stacked = pd.concat([left, right], ignore_index=True)

    out = (
        stacked.groupby("ticker", as_index=False)
        .agg(
            ticker_stress_sensitivity=("stress_corr_delta", "mean"),
            median_stress_sensitivity=("stress_corr_delta", "median"),
            calm_avg_corr=("avg_corr_calm", "mean"),
            stress_avg_corr=("avg_corr_stress", "mean"),
            pair_count=("stress_corr_delta", "size"),
        )
        .sort_values("ticker_stress_sensitivity", ascending=False)
        .reset_index(drop=True)
    )

    out["stress_sensitivity_rank"] = np.arange(1, len(out) + 1)

    return out


def summarize_latest_market_compression(
    pair_correlations: pd.DataFrame,
    pair_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare the latest available pair correlations to each pair's calm baseline.
    """

    if pair_correlations.empty or pair_summary.empty:
        return pd.DataFrame()

    latest_date = pair_correlations["date"].max()

    latest = pair_correlations[pair_correlations["date"] == latest_date].copy()

    baseline = pair_summary[
        ["ticker_a", "ticker_b", "avg_corr_calm", "avg_corr_stress"]
    ].copy()

    merged = latest.merge(baseline, on=["ticker_a", "ticker_b"], how="inner")

    if merged.empty:
        return pd.DataFrame()

    merged["latest_minus_calm"] = merged["corr"] - merged["avg_corr_calm"]
    merged["latest_minus_stress"] = merged["corr"] - merged["avg_corr_stress"]

    avg_corr_latest = float(merged["corr"].mean())
    avg_calm = float(merged["avg_corr_calm"].mean())
    avg_stress = float(merged["avg_corr_stress"].mean())
    market_compression_score = float(merged["latest_minus_calm"].mean())

    if market_compression_score >= 0.05:
        compression_state = "BROAD_COMPRESSION"
    elif market_compression_score >= 0.025:
        compression_state = "MODERATE_COMPRESSION"
    elif market_compression_score <= -0.05:
        compression_state = "BROAD_FRAGMENTATION"
    elif market_compression_score <= -0.025:
        compression_state = "MODERATE_FRAGMENTATION"
    else:
        compression_state = "STABLE"

    return pd.DataFrame(
        [
            {
                "date": latest_date,
                "regime": str(merged["regime"].iloc[0]).upper().strip(),
                "window": int(merged["window"].iloc[0]),
                "avg_corr_latest": avg_corr_latest,
                "avg_calm_baseline_corr": avg_calm,
                "avg_stress_baseline_corr": avg_stress,
                "market_compression_score": market_compression_score,
                "compression_state": compression_state,
                "pairs_above_calm_baseline": int(
                    (merged["latest_minus_calm"] > 0).sum()
                ),
                "pairs_below_calm_baseline": int(
                    (merged["latest_minus_calm"] < 0).sum()
                ),
                "pair_count": int(len(merged)),
            }
        ]
    )


def summarize_market_correlation_deformation(
    pair_correlations: pd.DataFrame,
    pair_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a date-level time series of market correlation deformation.

    Each date compares current pair correlations to each pair's calm baseline.

    Output:
        date
        regime
        window
        avg_corr
        avg_calm_baseline_corr
        avg_stress_baseline_corr
        market_compression_score
        compression_state
        pairs_above_calm_baseline
        pairs_below_calm_baseline
        pair_count
    """

    if pair_correlations.empty or pair_summary.empty:
        return pd.DataFrame()

    baseline = pair_summary[
        ["ticker_a", "ticker_b", "avg_corr_calm", "avg_corr_stress"]
    ].copy()

    merged = pair_correlations.merge(
        baseline,
        on=["ticker_a", "ticker_b"],
        how="inner",
    )

    if merged.empty:
        return pd.DataFrame()

    merged["latest_minus_calm"] = merged["corr"] - merged["avg_corr_calm"]
    merged["latest_minus_stress"] = merged["corr"] - merged["avg_corr_stress"]

    def classify(score: float) -> str:
        if score >= 0.05:
            return "BROAD_COMPRESSION"
        if score >= 0.025:
            return "MODERATE_COMPRESSION"
        if score <= -0.05:
            return "BROAD_FRAGMENTATION"
        if score <= -0.025:
            return "MODERATE_FRAGMENTATION"
        return "STABLE"

    out = (
        merged.groupby(["date", "regime", "window"], as_index=False)
        .agg(
            avg_corr=("corr", "mean"),
            avg_calm_baseline_corr=("avg_corr_calm", "mean"),
            avg_stress_baseline_corr=("avg_corr_stress", "mean"),
            market_compression_score=("latest_minus_calm", "mean"),
            stress_distance_score=("latest_minus_stress", "mean"),
            pairs_above_calm_baseline=(
                "latest_minus_calm",
                lambda x: int((x > 0).sum()),
            ),
            pairs_below_calm_baseline=(
                "latest_minus_calm",
                lambda x: int((x < 0).sum()),
            ),
            pair_count=("corr", "size"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    out["regime"] = out["regime"].astype(str).str.upper().str.strip()
    out["compression_state"] = out["market_compression_score"].apply(classify)

    out["compression_percentile"] = out["market_compression_score"].rank(
        pct=True,
        method="average",
    )

    out["fragmentation_percentile"] = 1.0 - out["market_compression_score"].rank(
        pct=True,
        method="average",
    )

    return out
