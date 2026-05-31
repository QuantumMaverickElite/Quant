from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from tabulate import tabulate

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.decision.entropy_decision import (
    apply_entropy_decision_columns,
    latest_entropy_decision,
)
from backtester.decision.market_state import build_market_state
from backtester.decision.volatility_decision import make_volatility_decision


def import_compute_garch_metrics():
    try:
        from backtester.analytics.garch import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.garch_metrics import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.volatility import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    raise ImportError(
        "Could not import compute_garch_metrics. "
        "Check src/backtester/analytics and update this script."
    )


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest a simple MarketState-driven portfolio allocator."
    )

    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        default=["SPY", "QQQ", "NVDA", "JPM", "XOM"],
        help="Ticker symbols to backtest.",
    )

    parser.add_argument(
        "--data-start",
        default="2018-01-01",
        help="Data start date used for indicators. Default: 2018-01-01",
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
        "--capital",
        type=float,
        default=10_000.0,
        help="Initial portfolio capital. Default: 10000",
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
        "--max-weight",
        type=float,
        default=0.35,
        help="Maximum weight per ticker. Default: 0.35",
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
        help="Rolling entropy z-score / percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of bins for return entropy. Default: 10",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/portfolio_backtest/market_state_v1",
        help="Output directory.",
    )

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact", "curves", "full"],
        default="full",
        help=(
            "Output mode. none=print only, compact=summary only, "
            "curves=summary+equity curve, full=summary+equity+rebalance log+plot. "
            "Default: full"
        ),
    )

    return parser.parse_args()


def download_price_data(
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


def compute_raw_momentum_score(prices: pd.DataFrame, asof_date: pd.Timestamp) -> float:
    close = prices.loc[:asof_date, "close"].dropna()

    if len(close) < 70:
        return 0.0

    ret_21 = close.iloc[-1] / close.iloc[-22] - 1.0
    ret_63 = close.iloc[-1] / close.iloc[-64] - 1.0

    raw_score = (0.40 * ret_21) + (0.60 * ret_63)

    return float(max(raw_score, 0.0))


def compute_market_state_for_date(
    prices: pd.DataFrame,
    asof_date: pd.Timestamp,
    entropy_config: EntropyConfig,
):
    compute_garch_metrics = import_compute_garch_metrics()

    hist = prices.loc[:asof_date].copy()

    if len(hist) < 320:
        raise ValueError("not enough history for entropy + volatility state")

    vol_price_series = hist[["close"]].copy()
    vol_metrics = compute_garch_metrics(vol_price_series)

    if vol_metrics.empty:
        raise ValueError("volatility metrics empty")

    latest_vol_row = vol_metrics.dropna().iloc[-1]
    volatility_decision = make_volatility_decision(latest_vol_row)

    entropy_metrics = compute_entropy_metrics(hist, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)

    entropy_decision = latest_entropy_decision(entropy_metrics)

    market_state = build_market_state(
        entropy_decision=entropy_decision,
        volatility_decision=volatility_decision,
    )

    return volatility_decision, entropy_decision, market_state


def assign_weights(
    rows: list[dict],
    max_weight: float,
) -> pd.DataFrame:
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["target_weight"] = 0.0

    allowed = (df["allow_new_equity_positions"] == True) & (df["adjusted_score"] > 0)

    allowed_df = df.loc[allowed].copy()

    if allowed_df.empty:
        return df

    score_sum = allowed_df["adjusted_score"].sum()

    if score_sum <= 0:
        return df

    target_gross_exposure = float(
        np.clip(allowed_df["combined_multiplier"].mean(), 0.0, 1.0)
    )

    raw_weights = (allowed_df["adjusted_score"] / score_sum) * target_gross_exposure

    capped_weights = raw_weights.clip(upper=max_weight)

    df.loc[allowed_df.index, "target_weight"] = capped_weights

    return df


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


def compute_portfolio_returns(
    data: dict[str, pd.DataFrame],
    weights_by_date: dict[pd.Timestamp, dict[str, float]],
    bt_start: str,
    bt_end: str,
    capital: float,
) -> pd.DataFrame:
    close = pd.concat(
        {ticker: df["close"] for ticker, df in data.items()},
        axis=1,
    ).sort_index()

    close = close.ffill()

    returns = close.pct_change().fillna(0.0)

    bt_start_ts = pd.Timestamp(bt_start)
    bt_end_ts = pd.Timestamp(bt_end)

    returns = returns[(returns.index >= bt_start_ts) & (returns.index < bt_end_ts)]

    if returns.empty:
        raise ValueError("No returns available in backtest window.")

    weights = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    weights[:] = np.nan

    for date, weight_map in weights_by_date.items():
        if date in weights.index:
            for ticker, weight in weight_map.items():
                if ticker in weights.columns:
                    weights.loc[date, ticker] = weight

    weights = weights.ffill().fillna(0.0)

    portfolio_returns = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)

    equity = capital * (1.0 + portfolio_returns).cumprod()

    out = pd.DataFrame(
        {
            "portfolio_return": portfolio_returns,
            "equity": equity,
        },
        index=returns.index,
    )

    return out


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def summarize_backtest(equity_curve: pd.DataFrame, capital: float) -> dict:
    start_equity = capital
    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return = final_equity / start_equity - 1.0

    days = len(equity_curve)
    years = days / 252.0

    if years > 0:
        cagr = (final_equity / start_equity) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0

    daily_returns = equity_curve["portfolio_return"]

    if daily_returns.std(ddof=0) > 0:
        sharpe = (daily_returns.mean() / daily_returns.std(ddof=0)) * np.sqrt(252)
    else:
        sharpe = 0.0

    return {
        "start_equity": start_equity,
        "final_equity": final_equity,
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": max_drawdown(equity_curve["equity"]) * 100,
        "sharpe": sharpe,
    }


def plot_equity_curve(equity_curve: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(equity_curve.index, equity_curve["equity"])
    ax.set_title("MarketState Portfolio Backtest Equity Curve")
    ax.set_ylabel("Equity")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_backtest(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    tickers = [ticker.upper() for ticker in args.tickers]

    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    data = download_price_data(
        tickers=tickers,
        data_start=args.data_start,
        bt_end=args.bt_end,
    )

    if not data:
        raise ValueError("No usable ticker data downloaded.")

    common_index = sorted(set().union(*[df.index for df in data.values()]))
    common_index = pd.DatetimeIndex(common_index)

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

    rebalance_logs = []
    weights_by_date: dict[pd.Timestamp, dict[str, float]] = {}

    for date in rebalance_dates:
        print(f"\nRebalancing on {date.date()}...")

        rows = []

        for ticker, prices in data.items():
            hist = prices.loc[:date]

            if hist.empty:
                continue

            try:
                raw_score = compute_raw_momentum_score(prices, date)

                _, entropy_decision, market_state = compute_market_state_for_date(
                    prices=prices,
                    asof_date=date,
                    entropy_config=entropy_config,
                )

                if not market_state.allow_new_equity_positions:
                    adjusted_score = 0.0
                else:
                    adjusted_score = raw_score * market_state.combined_multiplier

                rows.append(
                    {
                        "date": date,
                        "ticker": ticker,
                        "close": float(hist["close"].dropna().iloc[-1]),
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
                    }
                )

            except Exception as exc:
                rows.append(
                    {
                        "date": date,
                        "ticker": ticker,
                        "raw_score": 0.0,
                        "adjusted_score": 0.0,
                        "target_weight": 0.0,
                        "error": str(exc),
                    }
                )

        rebalance_df = assign_weights(rows, max_weight=args.max_weight)

        weight_map = {
            row["ticker"]: float(row["target_weight"])
            for _, row in rebalance_df.iterrows()
            if "target_weight" in row and pd.notna(row["target_weight"])
        }

        weights_by_date[date] = weight_map
        rebalance_logs.append(rebalance_df)

        display = rebalance_df.copy()
        for col in [
            "raw_score",
            "adjusted_score",
            "combined_multiplier",
            "target_weight",
        ]:
            if col in display.columns:
                display[col] = pd.to_numeric(display[col], errors="coerce").round(4)

        if "target_weight" in display.columns:
            display["target_weight"] = (display["target_weight"] * 100).round(2)

        cols = [
            "ticker",
            "vol_regime",
            "return_entropy_regime",
            "direction_entropy_regime",
            "raw_score",
            "adjusted_score",
            "combined_multiplier",
            "capital_posture",
            "target_weight",
        ]
        cols = [c for c in cols if c in display.columns]

        print(
            tabulate(display[cols], headers="keys", tablefmt="github", showindex=False)
        )

    rebalance_log = pd.concat(rebalance_logs, ignore_index=True)

    equity_curve = compute_portfolio_returns(
        data=data,
        weights_by_date=weights_by_date,
        bt_start=args.bt_start,
        bt_end=args.bt_end,
        capital=args.capital,
    )

    summary = summarize_backtest(equity_curve, capital=args.capital)

    return equity_curve, rebalance_log, summary


def main() -> None:
    args = parse_args()

    print("\nRunning MarketState Portfolio Backtest")
    print(f"Tickers: {', '.join([t.upper() for t in args.tickers])}")
    print(f"Data start: {args.data_start}")
    print(f"Backtest: {args.bt_start} to {args.bt_end}")
    print(f"Capital: ${args.capital:,.2f}")
    print(f"Rebalance: {args.rebalance}")
    print(f"Max weight: {args.max_weight:.2%}")
    print(f"Save mode: {args.save_mode}")

    equity_curve, rebalance_log, summary = run_backtest(args)

    print("\nBacktest Summary:")
    print(
        tabulate(
            pd.DataFrame([summary]).round(4),
            headers="keys",
            tablefmt="github",
            showindex=False,
        )
    )

    if args.save_mode != "none":
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_path = output_dir / "summary.csv"
        pd.DataFrame([summary]).to_csv(summary_path, index=False)

        saved = [("Summary", summary_path)]

        if args.save_mode in {"curves", "full"}:
            equity_path = output_dir / "equity_curve.csv"
            equity_curve.to_csv(equity_path)
            saved.append(("Equity curve", equity_path))

        if args.save_mode == "full":
            log_path = output_dir / "rebalance_log.csv"
            plot_path = output_dir / "equity_curve.png"
            rebalance_log.to_csv(log_path, index=False)
            plot_equity_curve(equity_curve, plot_path)
            saved.append(("Rebalance log", log_path))
            saved.append(("Plot", plot_path))

        print("\nSaved outputs:")
        for label, saved_path in saved:
            print(f"  {label}: {saved_path}")
    else:
        print("\nSave mode is none; no files written.")

    print("\nDone.")


if __name__ == "__main__":
    main()
