# src/backtester/correlation/spreads.py

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from backtester.correlation.io import prices_to_return_matrix


def compute_forward_or_trailing_returns(
    prices: pd.DataFrame,
    horizons: Sequence[int],
    *,
    trailing: bool = True,
) -> pd.DataFrame:
    """
    Compute trailing or forward returns from adjusted close prices.

    For mean reversion features, we usually want trailing returns:
        stock_return_5d = price_today / price_5_days_ago - 1

    Later, for evaluation, we may want forward returns:
        future_return_5d = price_5_days_later / price_today - 1
    """

    if prices.empty:
        raise ValueError("prices DataFrame is empty.")

    frame = prices.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    records: list[pd.DataFrame] = []

    for horizon in horizons:
        if horizon <= 0:
            raise ValueError("All horizons must be positive.")

        if trailing:
            returns = frame / frame.shift(horizon) - 1.0
            col_name = f"stock_return_{horizon}d"
        else:
            returns = frame.shift(-horizon) / frame - 1.0
            col_name = f"future_return_{horizon}d"

        melted = (
            returns.reset_index()
            .melt(
                id_vars=returns.index.name or "index",
                var_name="ticker",
                value_name=col_name,
            )
            .rename(columns={returns.index.name or "index": "date"})
        )

        melted["horizon"] = horizon
        records.append(melted)

    if not records:
        return pd.DataFrame()

    out = records[0]

    for nxt in records[1:]:
        out = out.merge(
            nxt,
            on=["date", "ticker", "horizon"],
            how="outer",
        )

    return out


def compute_peer_spread_features(
    prices: pd.DataFrame,
    correlation_features: pd.DataFrame,
    *,
    horizons: Sequence[int] = (5, 20),
    z_window: int = 60,
    peer_prefix: str = "peer_",
) -> pd.DataFrame:
    """
    Compute peer-relative return spread features.

    Output per date/ticker/horizon:
        stock_return_Xd
        peer_basket_return_Xd
        peer_spread_Xd
        peer_spread_z_Xd

    The peer basket is taken from the correlation feature rows for that same
    date/ticker/window.
    """

    if prices.empty:
        raise ValueError("prices DataFrame is empty.")

    if correlation_features.empty:
        raise ValueError("correlation_features is empty.")

    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    features = correlation_features.copy()
    features["date"] = pd.to_datetime(features["date"])

    peer_cols = _peer_columns(features, peer_prefix=peer_prefix)

    if not peer_cols:
        raise ValueError("No peer columns found in correlation_features.")

    all_outputs: list[pd.DataFrame] = []

    for horizon in horizons:
        stock_returns = prices / prices.shift(horizon) - 1.0

        stock_long = (
            stock_returns.reset_index()
            .melt(
                id_vars=stock_returns.index.name or "index",
                var_name="ticker",
                value_name=f"stock_return_{horizon}d",
            )
            .rename(columns={stock_returns.index.name or "index": "date"})
        )

        peer_basket = _compute_peer_basket_returns(
            stock_returns=stock_returns,
            correlation_features=features,
            peer_cols=peer_cols,
        )

        peer_basket = peer_basket.rename(
            columns={"peer_basket_return": f"peer_basket_return_{horizon}d"}
        )

        merged = features[
            ["date", "ticker", "window", "top_k_avg_corr"] + peer_cols
        ].merge(
            stock_long,
            on=["date", "ticker"],
            how="left",
        )

        merged = merged.merge(
            peer_basket,
            on=["date", "ticker", "window"],
            how="left",
        )

        stock_col = f"stock_return_{horizon}d"
        peer_col = f"peer_basket_return_{horizon}d"
        spread_col = "peer_spread"

        merged["stock_return"] = merged[stock_col]
        merged["peer_basket_return"] = merged[peer_col]
        merged["peer_spread"] = merged["stock_return"] - merged["peer_basket_return"]
        merged["horizon"] = horizon

        merged["peer_spread_z"] = _rolling_zscore_by_ticker(
            merged,
            value_col=spread_col,
            z_window=z_window,
        )

        keep_cols = [
            "date",
            "ticker",
            "window",
            "horizon",
            "top_k_avg_corr",
            "stock_return",
            "peer_basket_return",
            "peer_spread",
            "peer_spread_z",
        ] + peer_cols

        all_outputs.append(merged.loc[:, keep_cols])

    if not all_outputs:
        return pd.DataFrame()

    return pd.concat(all_outputs, ignore_index=True).sort_values(
        ["date", "window", "horizon", "ticker"]
    )


def _peer_columns(
    frame: pd.DataFrame,
    *,
    peer_prefix: str,
) -> list[str]:
    cols = []

    for col in frame.columns:
        if not col.startswith(peer_prefix):
            continue

        if col.endswith("_corr"):
            continue

        cols.append(col)

    return sorted(cols, key=_peer_col_sort_key)


def _peer_col_sort_key(col: str) -> int:
    try:
        return int(col.split("_")[1])
    except Exception:
        return 10_000


def _compute_peer_basket_returns(
    stock_returns: pd.DataFrame,
    correlation_features: pd.DataFrame,
    peer_cols: Sequence[str],
) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    available_tickers = set(stock_returns.columns)

    for row in correlation_features.itertuples(index=False):
        date = getattr(row, "date")
        ticker = getattr(row, "ticker")
        window = getattr(row, "window")

        if date not in stock_returns.index:
            records.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "window": window,
                    "peer_basket_return": np.nan,
                }
            )
            continue

        peer_values = []

        for peer_col in peer_cols:
            peer = getattr(row, peer_col)

            if peer is None or pd.isna(peer):
                continue

            if peer not in available_tickers:
                continue

            peer_values.append(stock_returns.at[date, peer])

        if peer_values:
            peer_return = float(np.nanmean(peer_values))
        else:
            peer_return = np.nan

        records.append(
            {
                "date": date,
                "ticker": ticker,
                "window": window,
                "peer_basket_return": peer_return,
            }
        )

    out = pd.DataFrame.from_records(records)

    # Rename after horizon is known by caller.
    return out


def _rolling_zscore_by_ticker(
    frame: pd.DataFrame,
    *,
    value_col: str,
    z_window: int,
) -> pd.Series:
    if z_window < 2:
        raise ValueError("z_window must be at least 2.")

    ordered = frame.sort_values(["ticker", "window", "horizon", "date"]).copy()

    grouped = ordered.groupby(["ticker", "window", "horizon"], group_keys=False)[
        value_col
    ]

    rolling_mean = grouped.transform(
        lambda s: s.rolling(z_window, min_periods=max(5, z_window // 4)).mean()
    )
    rolling_std = grouped.transform(
        lambda s: s.rolling(z_window, min_periods=max(5, z_window // 4)).std(ddof=1)
    )

    z = (ordered[value_col] - rolling_mean) / rolling_std.replace(0.0, np.nan)

    return z.reindex(frame.index)
