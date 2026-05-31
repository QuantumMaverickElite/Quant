from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from tabulate import tabulate

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.analytics.fast_volatility import compute_fast_volatility_metrics
from backtester.decision.entropy_decision import (
    EntropyDecision,
    apply_entropy_decision_columns,
)
from backtester.decision.market_state import build_market_state
from backtester.decision.volatility_decision import make_volatility_decision

DEFAULT_VOLATILE_UNIVERSE = [
    "QBTS",
    "RGTI",
    "IONQ",
    "QUBT",
    "OKLO",
    "SMR",
    "RKLB",
    "ACHR",
    "JOBY",
    "SOUN",
    "AI",
    "MSTR",
    "COIN",
    "MARA",
    "RIOT",
    "CLSK",
    "HUT",
    "BITF",
    "HOOD",
    "UPST",
    "AFRM",
    "CVNA",
    "RIVN",
    "LCID",
    "TSLA",
    "PLTR",
    "SMCI",
    "ARM",
    "NVDA",
    "AMD",
    "MU",
    "APP",
]


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build fast MarketState feature matrix for Monte Carlo simulation."
    )

    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        default=DEFAULT_VOLATILE_UNIVERSE,
        help="Ticker universe.",
    )

    parser.add_argument(
        "--data-start",
        default="2018-01-01",
        help="Data start date. Default: 2018-01-01",
    )

    parser.add_argument(
        "--bt-start",
        default="2025-01-01",
        help="Backtest start date. Default: 2025-01-01",
    )

    parser.add_argument(
        "--bt-end",
        default="2026-01-01",
        help="Backtest end date. Default: 2026-01-01",
    )

    parser.add_argument(
        "--rebalance",
        choices=["D", "W", "B", "3W", "M", "6W", "Q"],
        default="M",
        help=(
            "Rebalance frequency: D=daily, W=weekly, B=bi-weekly, 3W=every 3 weeks, M=monthly, 6W=every 6 weeks, Q=quarterly. "
            "Default: M"
        ),
    )

    parser.add_argument(
        "--entropy-window",
        type=int,
        default=60,
        help="Rolling entropy window. Default: 60",
    )

    parser.add_argument(
        "--zscore-window",
        type=int,
        default=252,
        help="Entropy/volatility percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of entropy bins. Default: 10",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/feature_matrix/market_state_v1",
        help="Output directory.",
    )

    return parser.parse_args()


def build_rebalance_dates(
    trading_index: pd.DatetimeIndex,
    bt_start: str,
    bt_end: str,
    freq: str,
) -> list[pd.Timestamp]:
    bt_start_ts = pd.Timestamp(bt_start)
    bt_end_ts = pd.Timestamp(bt_end)

    eligible = trading_index[
        (trading_index >= bt_start_ts) & (trading_index < bt_end_ts)
    ]

    if eligible.empty:
        return []

    if freq == "D":
        return [pd.Timestamp(date) for date in eligible]

    if freq in {"W", "B", "3W", "6W"}:
        weekly_groups = pd.Series(eligible, index=eligible).groupby(
            [eligible.year, eligible.isocalendar().week]
        )
        weekly_dates = [pd.Timestamp(group.iloc[0]) for _, group in weekly_groups]

        step_by_freq = {
            "W": 1,
            "B": 2,
            "3W": 3,
            "6W": 6,
        }
        step = step_by_freq[freq]

        return weekly_dates[::step]

    if freq == "M":
        groups = pd.Series(eligible, index=eligible).groupby(
            [eligible.year, eligible.month]
        )
    elif freq == "Q":
        groups = pd.Series(eligible, index=eligible).groupby(
            [eligible.year, eligible.quarter]
        )
    else:
        raise ValueError(f"Unsupported rebalance frequency: {freq}")

    # Rebalance on the first trading day of each calendar period.
    return [pd.Timestamp(group.iloc[0]) for _, group in groups]


def compute_raw_momentum_scores(prices: pd.DataFrame) -> pd.Series:
    close = prices["close"].astype(float)

    ret_21 = close / close.shift(21) - 1.0
    ret_63 = close / close.shift(63) - 1.0

    raw = (0.40 * ret_21) + (0.60 * ret_63)
    raw = raw.clip(lower=0.0)

    return raw


def entropy_decision_from_row(row: pd.Series) -> EntropyDecision:
    entropy_regime = row.get("entropy_regime", "UNKNOWN")
    direction_entropy_regime = row.get("direction_entropy_regime", "UNKNOWN")
    entropy_state = row.get("entropy_state", "UNKNOWN")
    entropy_state_description = row.get(
        "entropy_state_description",
        "No entropy state description available.",
    )

    normalized_entropy = row.get("normalized_entropy", float("nan"))
    entropy_zscore = row.get("entropy_zscore", float("nan"))
    entropy_percentile = row.get("entropy_percentile", float("nan"))

    normalized_direction_entropy = row.get("normalized_direction_entropy", float("nan"))
    direction_entropy_zscore = row.get("direction_entropy_zscore", float("nan"))
    direction_entropy_percentile = row.get("direction_entropy_percentile", float("nan"))

    signal_trust_multiplier = row.get("signal_trust_multiplier", 1.0)

    reason = (
        f"entropy_state={entropy_state}, "
        f"return_entropy_regime={entropy_regime}, "
        f"direction_entropy_regime={direction_entropy_regime}, "
        f"signal_trust_multiplier={signal_trust_multiplier:.2f}"
    )

    return EntropyDecision(
        entropy_regime=entropy_regime,
        direction_entropy_regime=direction_entropy_regime,
        entropy_state=entropy_state,
        entropy_state_description=entropy_state_description,
        normalized_entropy=normalized_entropy,
        entropy_zscore=entropy_zscore,
        entropy_percentile=entropy_percentile,
        normalized_direction_entropy=normalized_direction_entropy,
        direction_entropy_zscore=direction_entropy_zscore,
        direction_entropy_percentile=direction_entropy_percentile,
        signal_trust_multiplier=signal_trust_multiplier,
        allow_new_signals=True,
        reason=reason,
    )


def download_prices(
    tickers: list[str],
    data_start: str,
    bt_end: str,
) -> dict[str, pd.DataFrame]:
    data = {}

    for ticker in tickers:
        print(f"Downloading {ticker}...")

        df = yf.download(
            ticker,
            start=data_start,
            end=bt_end,
            auto_adjust=True,
            progress=False,
        )

        if df.empty:
            print(f"  WARNING: no data for {ticker}, skipping.")
            continue

        df = clean_yfinance_columns(df)

        if "close" not in df.columns:
            print(f"  WARNING: {ticker} missing close column, skipping.")
            continue

        data[ticker] = df

    return data


def build_feature_rows_for_ticker(
    ticker: str,
    prices: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
    entropy_config: EntropyConfig,
    zscore_window: int,
) -> list[dict]:
    rows = []

    close = prices["close"].dropna()

    if close.empty:
        return rows

    raw_scores = compute_raw_momentum_scores(prices)

    vol_metrics = compute_fast_volatility_metrics(
        prices[["close"]],
        price_col="close",
        zscore_window=zscore_window,
    )

    entropy_metrics = compute_entropy_metrics(prices, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)

    combined_index = prices.index.intersection(vol_metrics.index).intersection(
        entropy_metrics.index
    )

    prices = prices.loc[combined_index]
    vol_metrics = vol_metrics.loc[combined_index]
    entropy_metrics = entropy_metrics.loc[combined_index]
    raw_scores = raw_scores.loc[combined_index]

    for date in rebalance_dates:
        hist_idx = combined_index[combined_index <= date]

        if hist_idx.empty:
            continue

        asof_date = hist_idx[-1]

        vol_row = vol_metrics.loc[asof_date]
        ent_row = entropy_metrics.loc[asof_date]

        if pd.isna(vol_row.get("vol_percentile", np.nan)):
            continue

        if pd.isna(ent_row.get("entropy_percentile", np.nan)):
            continue

        if pd.isna(ent_row.get("direction_entropy_percentile", np.nan)):
            continue

        volatility_decision = make_volatility_decision(vol_row)
        entropy_decision = entropy_decision_from_row(ent_row)

        market_state = build_market_state(
            entropy_decision=entropy_decision,
            volatility_decision=volatility_decision,
        )

        raw_score = float(raw_scores.loc[asof_date])

        if not np.isfinite(raw_score):
            raw_score = 0.0

        if not market_state.allow_new_equity_positions:
            adjusted_score = 0.0
        else:
            adjusted_score = raw_score * market_state.combined_multiplier

        rows.append(
            {
                "date": pd.Timestamp(date),
                "asof_date": pd.Timestamp(asof_date),
                "ticker": ticker,
                "close": float(prices.loc[asof_date, "close"]),
                "raw_score": raw_score,
                "adjusted_score": adjusted_score,
                "vol_regime": market_state.volatility_regime,
                "return_entropy_regime": market_state.return_entropy_regime,
                "direction_entropy_regime": market_state.direction_entropy_regime,
                "entropy_state": market_state.entropy_state,
                "risk_multiplier": market_state.risk_multiplier,
                "signal_trust_multiplier": market_state.signal_trust_multiplier,
                "combined_multiplier": market_state.combined_multiplier,
                "allow_new_equity_positions": market_state.allow_new_equity_positions,
                "allow_options": market_state.allow_options,
                "capital_posture": market_state.capital_posture,
                "preferred_strategy": market_state.preferred_strategy,
                "vol_percentile": vol_row.get("vol_percentile", np.nan),
                "vol_zscore": vol_row.get("vol_zscore", np.nan),
                "entropy_percentile": ent_row.get("entropy_percentile", np.nan),
                "direction_entropy_percentile": ent_row.get(
                    "direction_entropy_percentile", np.nan
                ),
            }
        )

    return rows


def main() -> None:
    args = parse_args()

    tickers = sorted(set(t.upper() for t in args.tickers))

    print("\nBuilding MarketState Feature Matrix")
    print(f"Tickers: {len(tickers)}")
    print(f"Data start: {args.data_start}")
    print(f"Backtest window: {args.bt_start} to {args.bt_end}")
    print(f"Rebalance: {args.rebalance}")

    data = download_prices(
        tickers=tickers,
        data_start=args.data_start,
        bt_end=args.bt_end,
    )

    if not data:
        raise ValueError("No usable ticker data downloaded.")

    close_matrix = (
        pd.concat(
            {ticker: df["close"] for ticker, df in data.items()},
            axis=1,
        )
        .sort_index()
        .ffill()
    )

    common_index = pd.DatetimeIndex(
        sorted(set().union(*[df.index for df in data.values()]))
    )

    rebalance_dates = build_rebalance_dates(
        trading_index=common_index,
        bt_start=args.bt_start,
        bt_end=args.bt_end,
        freq=args.rebalance,
    )

    if not rebalance_dates:
        raise ValueError("No rebalance dates found.")

    print("\nRebalance dates:")
    print(", ".join(str(d.date()) for d in rebalance_dates))

    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    feature_rows = []

    for ticker, prices in data.items():
        print(f"Computing features for {ticker}...")

        rows = build_feature_rows_for_ticker(
            ticker=ticker,
            prices=prices,
            rebalance_dates=rebalance_dates,
            entropy_config=entropy_config,
            zscore_window=args.zscore_window,
        )

        feature_rows.extend(rows)

    features = pd.DataFrame(feature_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_path = output_dir / "market_state_features.csv"
    close_path = output_dir / "close_prices.csv"
    metadata_path = output_dir / "metadata.csv"

    features.to_csv(feature_path, index=False)
    close_matrix.to_csv(close_path)

    metadata = pd.DataFrame(
        [
            {
                "data_start": args.data_start,
                "bt_start": args.bt_start,
                "bt_end": args.bt_end,
                "rebalance": args.rebalance,
                "entropy_window": args.entropy_window,
                "zscore_window": args.zscore_window,
                "bins": args.bins,
                "tickers": " ".join(tickers),
            }
        ]
    )
    metadata.to_csv(metadata_path, index=False)

    print("\nFeature Matrix Summary:")
    summary = pd.DataFrame(
        [
            {
                "tickers_requested": len(tickers),
                "tickers_downloaded": len(data),
                "feature_rows": len(features),
                "rebalance_dates": len(rebalance_dates),
            }
        ]
    )
    print(tabulate(summary, headers="keys", tablefmt="github", showindex=False))

    if not features.empty:
        preview_cols = [
            "date",
            "ticker",
            "vol_regime",
            "return_entropy_regime",
            "direction_entropy_regime",
            "combined_multiplier",
            "capital_posture",
            "raw_score",
            "adjusted_score",
        ]
        preview_cols = [c for c in preview_cols if c in features.columns]

        print("\nPreview:")
        print(
            tabulate(
                features[preview_cols].tail(20),
                headers="keys",
                tablefmt="github",
                showindex=False,
            )
        )

    print("\nSaved outputs:")
    print(f"  Features: {feature_path}")
    print(f"  Prices:   {close_path}")
    print(f"  Metadata: {metadata_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
