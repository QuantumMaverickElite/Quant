# src/backtester/signals/mean_reversion.py

from __future__ import annotations

import numpy as np
import pandas as pd


def build_mean_reversion_signals(
    peer_spreads: pd.DataFrame,
    *,
    min_abs_z: float = 1.5,
    min_peer_corr: float = 0.30,
    long_only: bool = True,
) -> pd.DataFrame:
    """
    Convert peer-relative spread features into standardized mean reversion signals.

    Logic:
        negative peer_spread_z = stock underperformed peers
        positive peer_spread_z = stock outperformed peers

    For long-only:
        We only produce long signals when peer_spread_z is negative.

    Output:
        date
        ticker
        engine
        horizon
        raw_score
        normalized_score
        confidence
        direction
        peer_spread
        peer_spread_z
        top_k_avg_corr
    """

    required = {
        "date",
        "ticker",
        "window",
        "horizon",
        "top_k_avg_corr",
        "stock_return",
        "peer_basket_return",
        "peer_spread",
        "peer_spread_z",
    }

    missing = required - set(peer_spreads.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame = peer_spreads.copy()
    frame["date"] = pd.to_datetime(frame["date"])

    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(
        subset=[
            "peer_spread",
            "peer_spread_z",
            "top_k_avg_corr",
        ]
    )

    frame = frame[frame["top_k_avg_corr"] >= min_peer_corr].copy()

    if long_only:
        frame = frame[frame["peer_spread_z"] <= -min_abs_z].copy()
        frame["direction"] = "long"

        # More negative z-score should become a larger positive raw score.
        frame["raw_score"] = -frame["peer_spread_z"]
    else:
        frame = frame[frame["peer_spread_z"].abs() >= min_abs_z].copy()

        frame["direction"] = np.where(
            frame["peer_spread_z"] < 0,
            "long",
            "short",
        )

        frame["raw_score"] = frame["peer_spread_z"].abs()

    if frame.empty:
        return _empty_signal_frame()

    # Normalize score into a bounded rough 0-1 scale.
    # z=1.5 starts small, z=3+ becomes very strong.
    frame["normalized_score"] = (
        (frame["raw_score"] - min_abs_z) / (3.0 - min_abs_z)
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    # Confidence combines signal extremeness with peer relationship strength.
    # top_k_avg_corr already roughly measures whether this peer basket is meaningful.
    frame["confidence"] = (
        frame["normalized_score"] * frame["top_k_avg_corr"].clip(lower=0.0, upper=1.0)
    ).clip(lower=0.0, upper=1.0)

    frame["engine"] = "mean_reversion_peer_spread"

    keep_cols = [
        "date",
        "ticker",
        "engine",
        "window",
        "horizon",
        "direction",
        "raw_score",
        "normalized_score",
        "confidence",
        "stock_return",
        "peer_basket_return",
        "peer_spread",
        "peer_spread_z",
        "top_k_avg_corr",
    ]

    peer_cols = [
        col
        for col in frame.columns
        if col.startswith("peer_")
        and not col.endswith("_corr")
        and col.split("_")[-1].isdigit()
    ]

    out = frame.loc[:, keep_cols + peer_cols].sort_values(
        ["date", "horizon", "confidence", "ticker"],
        ascending=[True, True, False, True],
    )

    return out.reset_index(drop=True)


def _empty_signal_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "ticker",
            "engine",
            "window",
            "horizon",
            "direction",
            "raw_score",
            "normalized_score",
            "confidence",
            "stock_return",
            "peer_basket_return",
            "peer_spread",
            "peer_spread_z",
            "top_k_avg_corr",
        ]
    )
