# scripts/backtest_mean_reversion_daily_portfolio.py

from __future__ import annotations

import argparse
from dataclasses import dataclass
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


@dataclass
class OpenPosition:
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    shares: float
    entry_price: float
    entry_value: float
    adjusted_confidence: float
    signal_date: pd.Timestamp
    peer_spread_z: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Daily overlapping-position backtest for context-adjusted mean reversion signals."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/backtests/mean_reversion_daily_portfolio_h5",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)

    parser.add_argument("--signal-horizon", type=int, default=5)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--min-adjusted-confidence", type=float, default=0.10)
    parser.add_argument("--top-n-per-date", type=int, default=5)

    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument(
        "--max-gross-exposure",
        type=float,
        default=1.0,
        help="Maximum total market value of open positions divided by equity.",
    )
    parser.add_argument(
        "--target-new-basket-exposure",
        type=float,
        default=0.20,
        help="Target fraction of equity allocated to each new signal-day basket.",
    )
    parser.add_argument(
        "--max-position-weight",
        type=float,
        default=0.10,
        help="Maximum fraction of equity allocated to a single new position.",
    )
    parser.add_argument(
        "--fee-bps",
        type=float,
        default=5.0,
        help="One-way fee/slippage estimate in basis points on entry and exit.",
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


def prepare_orders(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    signal_horizon: int,
    hold_days: int,
    min_adjusted_confidence: float,
    top_n_per_date: int,
) -> pd.DataFrame:
    signals = signals.copy()
    signals["date"] = pd.to_datetime(signals["date"])

    signals = signals[
        (signals["horizon"] == signal_horizon)
        & (signals["adjusted_confidence"] >= min_adjusted_confidence)
    ].copy()

    if signals.empty:
        return pd.DataFrame()

    signals = signals.sort_values(
        ["date", "adjusted_confidence"],
        ascending=[True, False],
    )

    signals = signals.groupby("date", group_keys=False).head(top_n_per_date).copy()

    trading_dates = pd.DatetimeIndex(prices.index)
    date_to_idx = {pd.Timestamp(date): i for i, date in enumerate(trading_dates)}

    entry_dates = []
    exit_dates = []

    for signal_date in signals["date"]:
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

    signals["signal_date"] = signals["date"]
    signals["entry_date"] = entry_dates
    signals["exit_date"] = exit_dates

    signals = signals.dropna(subset=["entry_date", "exit_date"]).copy()

    return signals


def mark_to_market(
    positions: list[OpenPosition],
    prices: pd.DataFrame,
    date: pd.Timestamp,
) -> float:
    total = 0.0

    for pos in positions:
        price = prices.at[date, pos.ticker]
        if pd.isna(price):
            price = pos.entry_price
        total += pos.shares * float(price)

    return total


def run_daily_portfolio_backtest(
    orders: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    initial_capital: float,
    max_gross_exposure: float,
    target_new_basket_exposure: float,
    max_position_weight: float,
    fee_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    trading_dates = pd.DatetimeIndex(prices.index)
    fee_rate = fee_bps / 10_000.0

    orders = orders.copy()
    orders["entry_date"] = pd.to_datetime(orders["entry_date"])
    orders["exit_date"] = pd.to_datetime(orders["exit_date"])

    orders_by_entry = {
        date: group.copy() for date, group in orders.groupby("entry_date")
    }

    cash = float(initial_capital)
    open_positions: list[OpenPosition] = []

    equity_records: list[dict[str, object]] = []
    trade_records: list[dict[str, object]] = []

    for date in trading_dates:
        date = pd.Timestamp(date)

        # 1. Exit positions scheduled for today at today's close.
        remaining_positions: list[OpenPosition] = []

        for pos in open_positions:
            if pos.exit_date == date:
                exit_price = float(prices.at[date, pos.ticker])
                exit_value_before_fee = pos.shares * exit_price
                exit_fee = exit_value_before_fee * fee_rate
                exit_value_after_fee = exit_value_before_fee - exit_fee

                cash += exit_value_after_fee

                pnl = exit_value_after_fee - pos.entry_value
                trade_return = pnl / pos.entry_value if pos.entry_value else np.nan

                trade_records.append(
                    {
                        "signal_date": pos.signal_date,
                        "entry_date": pos.entry_date,
                        "exit_date": pos.exit_date,
                        "ticker": pos.ticker,
                        "shares": pos.shares,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "entry_value": pos.entry_value,
                        "exit_value": exit_value_after_fee,
                        "pnl": pnl,
                        "trade_return": trade_return,
                        "adjusted_confidence": pos.adjusted_confidence,
                        "peer_spread_z": pos.peer_spread_z,
                    }
                )
            else:
                remaining_positions.append(pos)

        open_positions = remaining_positions

        # 2. Mark current equity before new entries.
        open_value = mark_to_market(open_positions, prices, date)
        equity_before_entries = cash + open_value

        if equity_before_entries <= 0:
            raise RuntimeError(f"Equity went non-positive on {date.date()}.")

        current_gross_exposure = open_value / equity_before_entries

        # 3. Enter new positions scheduled for today.
        todays_orders = orders_by_entry.get(date)

        if todays_orders is not None and not todays_orders.empty:
            available_exposure = max(0.0, max_gross_exposure - current_gross_exposure)
            basket_exposure = min(target_new_basket_exposure, available_exposure)

            if basket_exposure > 0.0:
                todays_orders = todays_orders.copy()
                todays_orders["raw_weight"] = todays_orders["adjusted_confidence"].clip(
                    lower=0.0
                )

                raw_sum = todays_orders["raw_weight"].sum()

                if raw_sum > 0:
                    todays_orders["target_weight"] = (
                        basket_exposure * todays_orders["raw_weight"] / raw_sum
                    )
                    todays_orders["target_weight"] = todays_orders[
                        "target_weight"
                    ].clip(upper=max_position_weight)

                    # Re-normalize after per-position cap, but do not exceed basket exposure.
                    capped_sum = todays_orders["target_weight"].sum()
                    if capped_sum > basket_exposure:
                        todays_orders["target_weight"] *= basket_exposure / capped_sum

                    for order in todays_orders.itertuples(index=False):
                        ticker = order.ticker

                        if ticker not in prices.columns:
                            continue

                        entry_price = prices.at[date, ticker]
                        if pd.isna(entry_price) or entry_price <= 0:
                            continue

                        desired_value_before_fee = equity_before_entries * float(
                            order.target_weight
                        )
                        entry_fee = desired_value_before_fee * fee_rate
                        total_cash_required = desired_value_before_fee + entry_fee

                        if total_cash_required > cash:
                            desired_value_before_fee = cash / (1.0 + fee_rate)
                            entry_fee = desired_value_before_fee * fee_rate
                            total_cash_required = desired_value_before_fee + entry_fee

                        if desired_value_before_fee <= 0:
                            continue

                        shares = desired_value_before_fee / float(entry_price)
                        cash -= total_cash_required

                        open_positions.append(
                            OpenPosition(
                                ticker=ticker,
                                entry_date=date,
                                exit_date=pd.Timestamp(order.exit_date),
                                shares=float(shares),
                                entry_price=float(entry_price),
                                entry_value=float(desired_value_before_fee),
                                adjusted_confidence=float(order.adjusted_confidence),
                                signal_date=pd.Timestamp(order.signal_date),
                                peer_spread_z=float(order.peer_spread_z),
                            )
                        )

        # 4. End-of-day mark-to-market.
        open_value = mark_to_market(open_positions, prices, date)
        equity = cash + open_value
        gross_exposure = open_value / equity if equity > 0 else np.nan

        equity_records.append(
            {
                "date": date,
                "cash": cash,
                "open_value": open_value,
                "equity": equity,
                "gross_exposure": gross_exposure,
                "open_positions": len(open_positions),
            }
        )

    equity = pd.DataFrame(equity_records)
    trades = pd.DataFrame(trade_records)

    equity["daily_return"] = equity["equity"].pct_change().fillna(0.0)
    equity["cum_return"] = equity["equity"] / initial_capital - 1.0
    equity["running_max"] = equity["equity"].cummax()
    equity["drawdown"] = equity["equity"] / equity["running_max"] - 1.0

    return trades, equity


def summarize_daily_backtest(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    *,
    initial_capital: float,
) -> pd.DataFrame:
    daily_returns = equity["daily_return"].dropna()

    final_equity = float(equity["equity"].iloc[-1])
    total_return = final_equity / initial_capital - 1.0

    years = max((equity["date"].max() - equity["date"].min()).days / 365.25, 1e-9)
    cagr = (final_equity / initial_capital) ** (1.0 / years) - 1.0

    daily_vol = daily_returns.std(ddof=1)
    sharpe = np.nan
    if daily_vol and not np.isnan(daily_vol):
        sharpe = daily_returns.mean() / daily_vol * np.sqrt(252)

    summary = {
        "final_equity": final_equity,
        "total_return": total_return,
        "cagr": cagr,
        "daily_vol": daily_vol * np.sqrt(252),
        "sharpe": sharpe,
        "max_drawdown": float(equity["drawdown"].min()),
        "avg_gross_exposure": float(equity["gross_exposure"].mean()),
        "max_gross_exposure": float(equity["gross_exposure"].max()),
        "avg_open_positions": float(equity["open_positions"].mean()),
        "max_open_positions": float(equity["open_positions"].max()),
        "num_closed_trades": float(len(trades)),
    }

    if not trades.empty:
        summary.update(
            {
                "trade_win_rate": float((trades["pnl"] > 0).mean()),
                "avg_trade_return": float(trades["trade_return"].mean()),
                "median_trade_return": float(trades["trade_return"].median()),
                "avg_trade_pnl": float(trades["pnl"].mean()),
            }
        )

    return pd.DataFrame([summary])


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

    orders = prepare_orders(
        signals,
        prices,
        signal_horizon=args.signal_horizon,
        hold_days=args.hold_days,
        min_adjusted_confidence=args.min_adjusted_confidence,
        top_n_per_date=args.top_n_per_date,
    )

    if orders.empty:
        raise RuntimeError("No orders generated with current filters.")

    trades, equity = run_daily_portfolio_backtest(
        orders,
        prices,
        initial_capital=args.initial_capital,
        max_gross_exposure=args.max_gross_exposure,
        target_new_basket_exposure=args.target_new_basket_exposure,
        max_position_weight=args.max_position_weight,
        fee_bps=args.fee_bps,
    )

    summary = summarize_daily_backtest(
        trades,
        equity,
        initial_capital=args.initial_capital,
    )

    orders_path = out_dir / "orders.parquet"
    trades_path = out_dir / "closed_trades.parquet"
    equity_path = out_dir / "daily_equity.parquet"
    summary_path = out_dir / "summary.csv"

    orders.to_parquet(orders_path, index=False)
    trades.to_parquet(trades_path, index=False)
    equity.to_parquet(equity_path, index=False)
    summary.to_csv(summary_path, index=False)

    print()
    print("=" * 80)
    print("Daily Overlapping-Position Mean Reversion Backtest")
    print("=" * 80)
    print(f"Signals: {args.signals}")
    print(f"Signal horizon: {args.signal_horizon}")
    print(f"Hold days: {args.hold_days}")
    print(f"Min adjusted confidence: {args.min_adjusted_confidence}")
    print(f"Top N per date: {args.top_n_per_date}")
    print(f"Initial capital: ${args.initial_capital:,.2f}")
    print(f"Max gross exposure: {args.max_gross_exposure:.2f}")
    print(f"Target new basket exposure: {args.target_new_basket_exposure:.2f}")
    print(f"Max position weight: {args.max_position_weight:.2f}")
    print(f"Fee bps one-way: {args.fee_bps:.2f}")

    print()
    print("Saved:")
    print(f"  {orders_path}")
    print(f"  {trades_path}")
    print(f"  {equity_path}")
    print(f"  {summary_path}")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(summary.to_string(index=False))

    print()
    print("=" * 80)
    print("Latest daily equity")
    print("=" * 80)
    print(equity.tail(20).to_string(index=False))

    print()
    print("=" * 80)
    print("Latest closed trades")
    print("=" * 80)
    if trades.empty:
        print("No closed trades.")
    else:
        print(trades.tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
