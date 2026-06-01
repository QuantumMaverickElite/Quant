# scripts/backtest_mean_reversion_monte_carlo.py

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "ORCL",
    "AMD",
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "XOM",
    "CVX",
    "COP",
    "OXY",
    "WMT",
    "COST",
    "TGT",
    "HD",
    "LOW",
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "LLY",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest context-adjusted mean reversion signals with Monte Carlo bootstrap."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
        help="Context-adjusted mean reversion signal parquet file.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/backtests/mean_reversion_monte_carlo",
        help="Output directory.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker universe.",
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)

    parser.add_argument(
        "--signal-horizon",
        type=int,
        default=5,
        help="Use signals with this signal horizon.",
    )
    parser.add_argument(
        "--hold-days",
        type=int,
        default=5,
        help="Trading-day holding period after each signal date.",
    )
    parser.add_argument(
        "--min-adjusted-confidence",
        type=float,
        default=0.10,
        help="Minimum adjusted confidence required to trade.",
    )
    parser.add_argument(
        "--top-n-per-date",
        type=int,
        default=5,
        help="Maximum number of signals traded per date.",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10_000.0,
    )
    parser.add_argument(
        "--gross-exposure",
        type=float,
        default=1.0,
        help="Fraction of equity allocated across selected signals per rebalance.",
    )
    parser.add_argument(
        "--fee-bps",
        type=float,
        default=5.0,
        help="Round-trip trading cost in basis points per basket trade.",
    )
    parser.add_argument(
        "--mc-runs",
        type=int,
        default=1000,
        help="Number of Monte Carlo bootstrap paths.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    return parser.parse_args()


def download_adjusted_close(
    tickers: list[str],
    start: str,
    end: str | None,
) -> pd.DataFrame:
    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if data.empty:
        raise RuntimeError("No price data downloaded.")

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            raise RuntimeError("Downloaded data does not contain Close prices.")
        close = data["Close"]
    else:
        if "Close" not in data.columns:
            raise RuntimeError("Downloaded data does not contain Close prices.")
        close = data[["Close"]]
        close.columns = tickers

    close.index = pd.to_datetime(close.index)
    return close.sort_index()


def add_forward_trade_returns(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    hold_days: int,
) -> pd.DataFrame:
    """
    Add next-bar trade returns.

    Important timing rule:
        signal date = t
        entry date  = next trading day after t
        exit date   = entry date + hold_days

    This avoids using the same close that created the signal as the entry price.
    """

    if hold_days <= 0:
        raise ValueError("hold_days must be positive.")

    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    # Entry is next trading day's close.
    entry_prices = prices.shift(-1)

    # Exit is hold_days trading days after entry.
    exit_prices = prices.shift(-(hold_days + 1))

    trade_returns = exit_prices / entry_prices - 1.0

    trade_long = (
        trade_returns.reset_index()
        .melt(
            id_vars=trade_returns.index.name or "index",
            var_name="ticker",
            value_name="trade_return",
        )
        .rename(columns={trade_returns.index.name or "index": "date"})
    )

    signals = signals.copy()
    signals["date"] = pd.to_datetime(signals["date"])
    trade_long["date"] = pd.to_datetime(trade_long["date"])

    merged = signals.merge(
        trade_long,
        on=["date", "ticker"],
        how="left",
    )

    merged["entry_date"] = merged["date"].map(_next_trading_date_map(prices.index))
    merged["exit_date"] = merged["date"].map(
        _future_trading_date_map(prices.index, offset=hold_days + 1)
    )

    return merged.dropna(subset=["trade_return"]).copy()


def _next_trading_date_map(index: pd.DatetimeIndex) -> dict[pd.Timestamp, pd.Timestamp]:
    out: dict[pd.Timestamp, pd.Timestamp] = {}

    for i, date in enumerate(index):
        if i + 1 < len(index):
            out[pd.Timestamp(date)] = pd.Timestamp(index[i + 1])
        else:
            out[pd.Timestamp(date)] = pd.NaT

    return out


def _future_trading_date_map(
    index: pd.DatetimeIndex,
    *,
    offset: int,
) -> dict[pd.Timestamp, pd.Timestamp]:
    out: dict[pd.Timestamp, pd.Timestamp] = {}

    for i, date in enumerate(index):
        target = i + offset

        if target < len(index):
            out[pd.Timestamp(date)] = pd.Timestamp(index[target])
        else:
            out[pd.Timestamp(date)] = pd.NaT

    return out


def build_trade_baskets(
    signals: pd.DataFrame,
    *,
    signal_horizon: int,
    min_adjusted_confidence: float,
    top_n_per_date: int,
    gross_exposure: float,
    fee_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = signals.copy()

    required = {
        "date",
        "ticker",
        "horizon",
        "adjusted_confidence",
        "trade_return",
    }

    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame = frame[frame["horizon"] == signal_horizon].copy()
    frame = frame[frame["adjusted_confidence"] >= min_adjusted_confidence].copy()

    if frame.empty:
        return pd.DataFrame(), pd.DataFrame()

    frame = frame.sort_values(
        ["date", "adjusted_confidence"],
        ascending=[True, False],
    )

    selected = frame.groupby("date", group_keys=False).head(top_n_per_date).copy()

    selected["raw_weight"] = selected["adjusted_confidence"].clip(lower=0.0)

    weight_sum = selected.groupby("date")["raw_weight"].transform("sum")
    selected["portfolio_weight"] = np.where(
        weight_sum > 0.0,
        gross_exposure * selected["raw_weight"] / weight_sum,
        0.0,
    )

    selected["weighted_return"] = (
        selected["portfolio_weight"] * selected["trade_return"]
    )

    baskets = (
        selected.groupby("date")
        .agg(
            basket_return_before_cost=("weighted_return", "sum"),
            signal_count=("ticker", "count"),
            avg_adjusted_confidence=("adjusted_confidence", "mean"),
            max_adjusted_confidence=("adjusted_confidence", "max"),
        )
        .reset_index()
    )

    round_trip_cost = fee_bps / 10_000.0
    baskets["cost"] = round_trip_cost * gross_exposure
    baskets["basket_return"] = baskets["basket_return_before_cost"] - baskets["cost"]

    return selected, baskets


def build_equity_curve(
    baskets: pd.DataFrame,
    *,
    initial_capital: float,
) -> pd.DataFrame:
    equity = baskets.copy().sort_values("date")
    equity["growth"] = 1.0 + equity["basket_return"]
    equity["equity"] = initial_capital * equity["growth"].cumprod()
    equity["cum_return"] = equity["equity"] / initial_capital - 1.0
    equity["running_max"] = equity["equity"].cummax()
    equity["drawdown"] = equity["equity"] / equity["running_max"] - 1.0

    return equity


def summarize_equity(equity: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    if equity.empty:
        return {}

    returns = equity["basket_return"].dropna()

    total_return = equity["equity"].iloc[-1] / initial_capital - 1.0
    avg_return = returns.mean()
    vol = returns.std(ddof=1)

    sharpe_like = np.nan
    if vol and not np.isnan(vol):
        sharpe_like = avg_return / vol * np.sqrt(252 / 5)

    return {
        "num_rebalances": float(len(equity)),
        "final_equity": float(equity["equity"].iloc[-1]),
        "total_return": float(total_return),
        "mean_basket_return": float(avg_return),
        "median_basket_return": float(returns.median()),
        "win_rate": float((returns > 0).mean()),
        "max_drawdown": float(equity["drawdown"].min()),
        "sharpe_like": float(sharpe_like),
    }


def monte_carlo_bootstrap(
    basket_returns: pd.Series,
    *,
    initial_capital: float,
    runs: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    values = basket_returns.dropna().to_numpy(dtype=np.float64)

    if len(values) == 0:
        return pd.DataFrame()

    n = len(values)
    paths = np.empty((runs, n), dtype=np.float64)

    for i in range(runs):
        sampled = rng.choice(values, size=n, replace=True)
        paths[i] = initial_capital * np.cumprod(1.0 + sampled)

    final_equity = paths[:, -1]
    total_return = final_equity / initial_capital - 1.0

    max_drawdowns = []
    for i in range(runs):
        running_max = np.maximum.accumulate(paths[i])
        dd = paths[i] / running_max - 1.0
        max_drawdowns.append(dd.min())

    return pd.DataFrame(
        {
            "run": np.arange(runs),
            "final_equity": final_equity,
            "total_return": total_return,
            "max_drawdown": max_drawdowns,
        }
    )


def summarize_monte_carlo(mc: pd.DataFrame) -> pd.DataFrame:
    if mc.empty:
        return pd.DataFrame()

    rows = []

    for col in ["final_equity", "total_return", "max_drawdown"]:
        vals = mc[col].dropna()
        rows.append(
            {
                "metric": col,
                "mean": vals.mean(),
                "median": vals.median(),
                "p05": vals.quantile(0.05),
                "p25": vals.quantile(0.25),
                "p75": vals.quantile(0.75),
                "p95": vals.quantile(0.95),
                "min": vals.min(),
                "max": vals.max(),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    signal_path = Path(args.signals)

    if not signal_path.exists():
        raise FileNotFoundError(f"Signal file not found: {signal_path}")

    signals = pd.read_parquet(signal_path)

    if signals.empty:
        raise RuntimeError("Signal file is empty.")

    tickers = list(dict.fromkeys(args.tickers))

    prices = download_adjusted_close(
        tickers=tickers,
        start=args.start,
        end=args.end,
    )

    trade_signals = add_forward_trade_returns(
        signals=signals,
        prices=prices,
        hold_days=args.hold_days,
    )

    trades, baskets = build_trade_baskets(
        trade_signals,
        signal_horizon=args.signal_horizon,
        min_adjusted_confidence=args.min_adjusted_confidence,
        top_n_per_date=args.top_n_per_date,
        gross_exposure=args.gross_exposure,
        fee_bps=args.fee_bps,
    )

    if trades.empty or baskets.empty:
        raise RuntimeError("No trades generated with current filters.")

    equity = build_equity_curve(
        baskets,
        initial_capital=args.initial_capital,
    )

    summary = summarize_equity(
        equity,
        initial_capital=args.initial_capital,
    )

    mc = monte_carlo_bootstrap(
        equity["basket_return"],
        initial_capital=args.initial_capital,
        runs=args.mc_runs,
        seed=args.seed,
    )

    mc_summary = summarize_monte_carlo(mc)

    trades_path = out_dir / "trades.parquet"
    baskets_path = out_dir / "baskets.parquet"
    equity_path = out_dir / "equity.parquet"
    summary_path = out_dir / "summary.csv"
    mc_path = out_dir / "monte_carlo.parquet"
    mc_summary_path = out_dir / "monte_carlo_summary.csv"

    trades.to_parquet(trades_path, index=False)
    baskets.to_parquet(baskets_path, index=False)
    equity.to_parquet(equity_path, index=False)
    pd.DataFrame([summary]).to_csv(summary_path, index=False)
    mc.to_parquet(mc_path, index=False)
    mc_summary.to_csv(mc_summary_path, index=False)

    print()
    print("=" * 80)
    print("Mean Reversion Trading Simulation")
    print("=" * 80)
    print(f"Signals: {args.signals}")
    print(f"Signal horizon: {args.signal_horizon}")
    print(f"Hold days: {args.hold_days}")
    print(f"Min adjusted confidence: {args.min_adjusted_confidence}")
    print(f"Top N per date: {args.top_n_per_date}")
    print(f"Initial capital: ${args.initial_capital:,.2f}")
    print(f"Gross exposure: {args.gross_exposure:.2f}")
    print(f"Fee bps: {args.fee_bps:.2f}")
    print()
    print("Saved:")
    print(f"  {trades_path}")
    print(f"  {baskets_path}")
    print(f"  {equity_path}")
    print(f"  {summary_path}")
    print(f"  {mc_path}")
    print(f"  {mc_summary_path}")

    print()
    print("=" * 80)
    print("Backtest Summary")
    print("=" * 80)
    print(pd.DataFrame([summary]).to_string(index=False))

    print()
    print("=" * 80)
    print("Monte Carlo Summary")
    print("=" * 80)
    print(mc_summary.to_string(index=False))

    print()
    print("=" * 80)
    print("Latest Baskets")
    print("=" * 80)
    print(baskets.tail(20).to_string(index=False))

    print()
    print("=" * 80)
    print("Latest Trades")
    print("=" * 80)
    display_cols = [
        "date",
        "entry_date",
        "exit_date" "ticker",
        "horizon",
        "adjusted_confidence",
        "trade_return",
        "peer_spread_z",
        "context_weight",
        "volatility_state",
        "entropy_state",
        "peer_1",
        "peer_2",
        "peer_3",
        "peer_4",
        "peer_5",
    ]
    display_cols = [col for col in display_cols if col in trades.columns]
    print(
        trades.sort_values("date").tail(30).loc[:, display_cols].to_string(index=False)
    )


if __name__ == "__main__":
    main()
