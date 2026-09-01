from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
from tabulate import tabulate

from backtester.analytics.entropy import EntropyConfig
from backtester.backtests.market_state_portfolio import (
    assign_weights,
    build_rebalance_dates,
    compute_market_state_for_date,
    compute_portfolio_returns,
    compute_raw_momentum_score,
    import_compute_garch_metrics,
    max_drawdown,
    summarize_backtest,
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
