# scripts/stress_mean_reversion_monte_carlo.py

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_SIGNAL_TICKERS = [
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
        description="GPU-capable Monte Carlo stress test for mean reversion signals."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/stress/mean_reversion_h100",
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)

    parser.add_argument("--signal-horizon", type=int, default=100)
    parser.add_argument("--hold-days", type=int, default=100)
    parser.add_argument("--min-adjusted-confidence", type=float, default=0.10)
    parser.add_argument("--top-n-per-date", type=int, default=5)

    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=5.0)

    parser.add_argument(
        "--universe-file",
        default=None,
        help="Optional text file with one ticker per line for broad random controls.",
    )
    parser.add_argument(
        "--extra-tickers",
        nargs="*",
        default=[],
        help="Extra tickers to include in the random control universe.",
    )
    parser.add_argument(
        "--mc-runs",
        type=int,
        default=10_000,
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "numpy", "cupy"],
        default="auto",
    )
    parser.add_argument("--seed", type=int, default=42)

    return parser.parse_args()


def get_xp(backend: str):
    if backend == "numpy":
        return np, "numpy"

    if backend in {"auto", "cupy"}:
        try:
            import cupy as cp

            _ = cp.asarray([1.0]).sum().get()
            return cp, "cupy"
        except Exception:
            if backend == "cupy":
                raise

    return np, "numpy"


def to_cpu(arr):
    if hasattr(arr, "get"):
        return arr.get()
    return np.asarray(arr)


def load_universe(args: argparse.Namespace, signal_tickers: list[str]) -> list[str]:
    tickers: list[str] = []

    if args.universe_file:
        path = Path(args.universe_file)
        if not path.exists():
            raise FileNotFoundError(f"Universe file not found: {path}")

        tickers.extend(
            line.strip().upper()
            for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    tickers.extend(args.extra_tickers)
    tickers.extend(signal_tickers)
    tickers.extend(DEFAULT_SIGNAL_TICKERS)

    cleaned = []
    seen = set()

    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue

        # yfinance uses BRK-B instead of BRK.B style in many cases.
        ticker = ticker.replace(".", "-")

        if ticker not in seen:
            cleaned.append(ticker)
            seen.add(ticker)

    return cleaned


def download_adjusted_close(
    tickers: list[str],
    start: str,
    end: str | None,
) -> pd.DataFrame:
    print(f"Downloading {len(tickers):,} tickers...")

    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=True,
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
        close.columns = tickers[:1]

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()

    # Drop columns with no usable price history.
    close = close.dropna(axis=1, how="all")

    return close


def prepare_signal_orders(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    signal_horizon: int,
    hold_days: int,
    min_adjusted_confidence: float,
    top_n_per_date: int,
) -> pd.DataFrame:
    frame = signals.copy()
    frame["date"] = pd.to_datetime(frame["date"])

    frame = frame[
        (frame["horizon"] == signal_horizon)
        & (frame["adjusted_confidence"] >= min_adjusted_confidence)
    ].copy()

    if frame.empty:
        return pd.DataFrame()

    frame = frame.sort_values(
        ["date", "adjusted_confidence"],
        ascending=[True, False],
    )

    frame = frame.groupby("date", group_keys=False).head(top_n_per_date).copy()

    trading_dates = pd.DatetimeIndex(prices.index)
    date_to_idx = {pd.Timestamp(date): i for i, date in enumerate(trading_dates)}

    entry_dates = []
    exit_dates = []

    for signal_date in frame["date"]:
        idx = date_to_idx.get(pd.Timestamp(signal_date))

        if idx is None:
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            continue

        entry_idx = idx + 1
        exit_idx = idx + 1 + hold_days

        if entry_idx >= len(trading_dates) or exit_idx >= len(trading_dates):
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            continue

        entry_dates.append(pd.Timestamp(trading_dates[entry_idx]))
        exit_dates.append(pd.Timestamp(trading_dates[exit_idx]))

    frame["signal_date"] = frame["date"]
    frame["entry_date"] = entry_dates
    frame["exit_date"] = exit_dates

    frame = frame.dropna(subset=["entry_date", "exit_date"]).copy()

    return frame


def build_forward_return_matrix(
    prices: pd.DataFrame,
    *,
    hold_days: int,
) -> pd.DataFrame:
    entry_prices = prices.shift(-1)
    exit_prices = prices.shift(-(hold_days + 1))
    returns = exit_prices / entry_prices - 1.0
    returns = returns.replace([np.inf, -np.inf], np.nan)
    return returns


def actual_basket_returns(
    orders: pd.DataFrame,
    fwd_returns: pd.DataFrame,
    *,
    fee_bps: float,
) -> pd.DataFrame:
    rows = []
    fee = fee_bps / 10_000.0

    for date, group in orders.groupby("signal_date"):
        weights = (
            group["adjusted_confidence"].clip(lower=0.0).to_numpy(dtype=np.float64)
        )

        if weights.sum() <= 0:
            continue

        weights = weights / weights.sum()

        returns = []

        for row in group.itertuples(index=False):
            ticker = row.ticker

            if ticker not in fwd_returns.columns:
                returns.append(np.nan)
                continue

            returns.append(fwd_returns.at[pd.Timestamp(row.signal_date), ticker])

        returns_arr = np.asarray(returns, dtype=np.float64)
        mask = np.isfinite(returns_arr)

        if not mask.any():
            continue

        weights = weights[mask]
        weights = weights / weights.sum()

        basket_return = float(np.sum(weights * returns_arr[mask]) - fee)

        rows.append(
            {
                "date": pd.Timestamp(date),
                "basket_return": basket_return,
                "signal_count": int(mask.sum()),
                "avg_adjusted_confidence": float(group["adjusted_confidence"].mean()),
                "max_adjusted_confidence": float(group["adjusted_confidence"].max()),
            }
        )

    return pd.DataFrame(rows).sort_values("date")


def equity_from_returns(
    returns: np.ndarray,
    *,
    initial_capital: float,
) -> tuple[float, float, float, float]:
    equity = initial_capital * np.cumprod(1.0 + returns)
    final_equity = float(equity[-1])
    total_return = final_equity / initial_capital - 1.0

    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min())

    win_rate = float((returns > 0).mean())

    return final_equity, total_return, max_drawdown, win_rate


def monte_carlo_same_dates_random_tickers(
    fwd_returns: pd.DataFrame,
    orders: pd.DataFrame,
    *,
    initial_capital: float,
    fee_bps: float,
    runs: int,
    xp,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    universe = list(fwd_returns.columns)
    ticker_to_idx = {ticker: i for i, ticker in enumerate(universe)}

    signal_dates = []
    counts = []

    for date, group in orders.groupby("signal_date"):
        if pd.Timestamp(date) not in fwd_returns.index:
            continue

        signal_dates.append(pd.Timestamp(date))
        counts.append(len(group))

    if not signal_dates:
        return pd.DataFrame()

    date_indices = [fwd_returns.index.get_loc(date) for date in signal_dates]
    ret_matrix_cpu = fwd_returns.to_numpy(dtype=np.float32)

    ret_matrix = xp.asarray(np.nan_to_num(ret_matrix_cpu, nan=np.nan), dtype=xp.float32)

    results = []

    n_tickers = len(universe)
    fee = fee_bps / 10_000.0

    for run in range(runs):
        basket_returns = []

        for date_idx, count in zip(date_indices, counts):
            count = max(1, min(int(count), n_tickers))

            sampled = rng.choice(n_tickers, size=count, replace=False)
            sampled_xp = xp.asarray(sampled, dtype=xp.int32)

            vals = ret_matrix[date_idx, sampled_xp]
            vals_cpu = to_cpu(vals)

            vals_cpu = vals_cpu[np.isfinite(vals_cpu)]

            if len(vals_cpu) == 0:
                basket_returns.append(0.0)
            else:
                basket_returns.append(float(np.mean(vals_cpu) - fee))

        returns = np.asarray(basket_returns, dtype=np.float64)
        final_equity, total_return, max_drawdown, win_rate = equity_from_returns(
            returns,
            initial_capital=initial_capital,
        )

        results.append(
            {
                "run": run,
                "test": "same_dates_random_tickers",
                "final_equity": final_equity,
                "total_return": total_return,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
            }
        )

    return pd.DataFrame(results)


def monte_carlo_random_dates_random_tickers(
    fwd_returns: pd.DataFrame,
    orders: pd.DataFrame,
    *,
    initial_capital: float,
    fee_bps: float,
    runs: int,
    xp,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)

    counts = [len(group) for _, group in orders.groupby("signal_date")]
    n_baskets = len(counts)

    valid = fwd_returns.dropna(axis=0, how="all")
    ret_matrix_cpu = valid.to_numpy(dtype=np.float32)

    n_dates, n_tickers = ret_matrix_cpu.shape
    ret_matrix = xp.asarray(np.nan_to_num(ret_matrix_cpu, nan=np.nan), dtype=xp.float32)

    fee = fee_bps / 10_000.0
    results = []

    for run in range(runs):
        basket_returns = []

        sampled_dates = rng.choice(n_dates, size=n_baskets, replace=True)

        for date_idx, count in zip(sampled_dates, counts):
            count = max(1, min(int(count), n_tickers))

            sampled_tickers = rng.choice(n_tickers, size=count, replace=False)
            sampled_xp = xp.asarray(sampled_tickers, dtype=xp.int32)

            vals = ret_matrix[date_idx, sampled_xp]
            vals_cpu = to_cpu(vals)
            vals_cpu = vals_cpu[np.isfinite(vals_cpu)]

            if len(vals_cpu) == 0:
                basket_returns.append(0.0)
            else:
                basket_returns.append(float(np.mean(vals_cpu) - fee))

        returns = np.asarray(basket_returns, dtype=np.float64)
        final_equity, total_return, max_drawdown, win_rate = equity_from_returns(
            returns,
            initial_capital=initial_capital,
        )

        results.append(
            {
                "run": run,
                "test": "random_dates_random_tickers",
                "final_equity": final_equity,
                "total_return": total_return,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
            }
        )

    return pd.DataFrame(results)


def summarize_distribution(mc: pd.DataFrame, actual: dict[str, float]) -> pd.DataFrame:
    rows = []

    for test, group in mc.groupby("test"):
        vals = group["total_return"].dropna()

        rows.append(
            {
                "test": test,
                "runs": len(vals),
                "actual_total_return": actual["total_return"],
                "mc_mean_total_return": vals.mean(),
                "mc_median_total_return": vals.median(),
                "mc_p05_total_return": vals.quantile(0.05),
                "mc_p95_total_return": vals.quantile(0.95),
                "actual_percentile": float((vals < actual["total_return"]).mean()),
                "prob_random_beats_actual": float(
                    (vals >= actual["total_return"]).mean()
                ),
            }
        )

    return pd.DataFrame(rows).sort_values("prob_random_beats_actual")


def year_exclusion_stress(
    basket_returns: pd.DataFrame,
    *,
    initial_capital: float,
) -> pd.DataFrame:
    frame = basket_returns.copy()
    frame["year"] = frame["date"].dt.year

    rows = []

    all_years = sorted(frame["year"].unique().tolist())

    for year in all_years:
        subset = frame[frame["year"] != year].copy()

        if subset.empty:
            continue

        returns = subset["basket_return"].to_numpy(dtype=np.float64)
        final_equity, total_return, max_drawdown, win_rate = equity_from_returns(
            returns,
            initial_capital=initial_capital,
        )

        rows.append(
            {
                "excluded_year": year,
                "num_baskets": len(subset),
                "final_equity": final_equity,
                "total_return": total_return,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
            }
        )

    return pd.DataFrame(rows)


def ticker_exclusion_stress(
    orders: pd.DataFrame,
    fwd_returns: pd.DataFrame,
    *,
    initial_capital: float,
    fee_bps: float,
) -> pd.DataFrame:
    rows = []
    tickers = sorted(orders["ticker"].unique().tolist())

    base = actual_basket_returns(orders, fwd_returns, fee_bps=fee_bps)

    if base.empty:
        return pd.DataFrame()

    for ticker in tickers:
        subset_orders = orders[orders["ticker"] != ticker].copy()

        if subset_orders.empty:
            continue

        baskets = actual_basket_returns(subset_orders, fwd_returns, fee_bps=fee_bps)

        if baskets.empty:
            continue

        returns = baskets["basket_return"].to_numpy(dtype=np.float64)
        final_equity, total_return, max_drawdown, win_rate = equity_from_returns(
            returns,
            initial_capital=initial_capital,
        )

        rows.append(
            {
                "excluded_ticker": ticker,
                "num_baskets": len(baskets),
                "final_equity": final_equity,
                "total_return": total_return,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
            }
        )

    return pd.DataFrame(rows).sort_values("total_return")


def main() -> None:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    xp, backend_name = get_xp(args.backend)

    print(f"Using backend: {backend_name}")

    signals = pd.read_parquet(args.signals)
    signals["date"] = pd.to_datetime(signals["date"])

    signal_tickers = sorted(signals["ticker"].unique().tolist())
    universe = load_universe(args, signal_tickers)

    prices = download_adjusted_close(
        universe,
        start=args.start,
        end=args.end,
    )

    orders = prepare_signal_orders(
        signals,
        prices,
        signal_horizon=args.signal_horizon,
        hold_days=args.hold_days,
        min_adjusted_confidence=args.min_adjusted_confidence,
        top_n_per_date=args.top_n_per_date,
    )

    if orders.empty:
        raise RuntimeError("No orders generated with current filters.")

    fwd_returns = build_forward_return_matrix(
        prices,
        hold_days=args.hold_days,
    )

    actual_baskets = actual_basket_returns(
        orders,
        fwd_returns,
        fee_bps=args.fee_bps,
    )

    actual_returns = actual_baskets["basket_return"].to_numpy(dtype=np.float64)

    actual_final_equity, actual_total_return, actual_max_drawdown, actual_win_rate = (
        equity_from_returns(
            actual_returns,
            initial_capital=args.initial_capital,
        )
    )

    actual_summary = {
        "final_equity": actual_final_equity,
        "total_return": actual_total_return,
        "max_drawdown": actual_max_drawdown,
        "win_rate": actual_win_rate,
        "num_baskets": len(actual_baskets),
        "num_orders": len(orders),
        "num_universe_tickers": len(prices.columns),
        "backend": backend_name,
    }

    same_date_mc = monte_carlo_same_dates_random_tickers(
        fwd_returns,
        orders,
        initial_capital=args.initial_capital,
        fee_bps=args.fee_bps,
        runs=args.mc_runs,
        xp=xp,
        seed=args.seed,
    )

    random_date_mc = monte_carlo_random_dates_random_tickers(
        fwd_returns,
        orders,
        initial_capital=args.initial_capital,
        fee_bps=args.fee_bps,
        runs=args.mc_runs,
        xp=xp,
        seed=args.seed,
    )

    mc = pd.concat([same_date_mc, random_date_mc], ignore_index=True)
    mc_summary = summarize_distribution(mc, actual_summary)

    year_stress = year_exclusion_stress(
        actual_baskets,
        initial_capital=args.initial_capital,
    )

    ticker_stress = ticker_exclusion_stress(
        orders,
        fwd_returns,
        initial_capital=args.initial_capital,
        fee_bps=args.fee_bps,
    )

    orders.to_parquet(out_dir / "orders.parquet", index=False)
    actual_baskets.to_parquet(out_dir / "actual_baskets.parquet", index=False)
    pd.DataFrame([actual_summary]).to_csv(out_dir / "actual_summary.csv", index=False)
    mc.to_parquet(out_dir / "monte_carlo_controls.parquet", index=False)
    mc_summary.to_csv(out_dir / "monte_carlo_control_summary.csv", index=False)
    year_stress.to_csv(out_dir / "year_exclusion_stress.csv", index=False)
    ticker_stress.to_csv(out_dir / "ticker_exclusion_stress.csv", index=False)

    print()
    print("=" * 80)
    print("Mean Reversion Monte Carlo Stress Test")
    print("=" * 80)
    print(f"Backend: {backend_name}")
    print(f"Universe tickers downloaded: {len(prices.columns):,}")
    print(f"Orders: {len(orders):,}")
    print(f"Baskets: {len(actual_baskets):,}")
    print(f"MC runs per control: {args.mc_runs:,}")

    print()
    print("=" * 80)
    print("Actual Strategy Summary")
    print("=" * 80)
    print(pd.DataFrame([actual_summary]).to_string(index=False))

    print()
    print("=" * 80)
    print("Monte Carlo Control Summary")
    print("=" * 80)
    print(mc_summary.to_string(index=False))

    print()
    print("=" * 80)
    print("Year Exclusion Stress")
    print("=" * 80)
    print(year_stress.to_string(index=False))

    print()
    print("=" * 80)
    print("Ticker Exclusion Stress: worst after excluding ticker")
    print("=" * 80)
    print(ticker_stress.head(20).to_string(index=False))

    print()
    print("=" * 80)
    print("Ticker Exclusion Stress: best after excluding ticker")
    print("=" * 80)
    print(ticker_stress.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
