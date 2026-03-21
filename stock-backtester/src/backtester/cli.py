from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtester.data import fetch_prices
from backtester.engines.event_engine import run_dividend_strategy
from backtester.engines.position_engine import run_backtest
from backtester.metrics import summary
from backtester.plot import plot_equity
from backtester.strategies import regime_positions


def main() -> None:
    p = argparse.ArgumentParser(
        description="Stock backtester with regime and dividend strategy support."
    )

    p.add_argument(
        "--strategy",
        choices=["regime", "dividend"],
        default="regime",
        help="Which strategy engine to run.",
    )

    p.add_argument("--ticker", default="SPY")
    p.add_argument(
        "--tickers",
        nargs="+",
        help="Ticker list for dividend strategy, e.g. PG KO JNJ XOM CVX",
    )

    p.add_argument("--start", default="2005-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--fee-bps", type=float, default=2.0)

    # Regime strategy params
    p.add_argument(
        "--lookback",
        type=int,
        default=50,
        help="Lookback days for momentum filter (regime strategy).",
    )
    p.add_argument(
        "--down-days",
        type=int,
        default=2,
        help="Buy after N down days in a row (regime strategy).",
    )
    p.add_argument(
        "--up-days",
        type=int,
        default=1,
        help="Sell after N up days in a row (regime strategy).",
    )
    p.add_argument(
        "--crash-week-drop",
        type=float,
        default=0.08,
        help="Trigger crash mode if 5-day return <= -this (regime strategy).",
    )
    p.add_argument(
        "--crash-hold-days",
        type=int,
        default=5,
        help="Keep crash mode active for this many trading days after trigger.",
    )
    p.add_argument(
        "--crash-down-days",
        type=int,
        default=1,
        help="Buy streak during crash mode (regime strategy).",
    )
    p.add_argument(
        "--crash-up-days",
        type=int,
        default=1,
        help="Sell streak during crash mode (regime strategy).",
    )
    p.add_argument(
        "--down-leverage",
        type=float,
        default=1.3,
        help="Exposure when mom <= 0 and long (regime strategy).",
    )
    p.add_argument(
        "--allow-leverage-in-crash",
        action="store_true",
        help="If set, leverage is also applied during crash mode.",
    )

    # Dividend strategy params
    p.add_argument(
        "--hold-days",
        type=int,
        default=1,
        help="Sell N trading days after ex-date (dividend strategy).",
    )
    p.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="Capital per trade for dividend strategy.",
    )

    p.add_argument("--debug", action="store_true", help="Print sanity checks.")
    args = p.parse_args()

    Path("outputs").mkdir(exist_ok=True)

    if args.strategy == "dividend":
        if not args.tickers:
            raise ValueError("--tickers is required when --strategy dividend is used.")

        tickers = [t.upper() for t in args.tickers]

        trades_df = run_dividend_strategy(
            tickers=tickers,
            start=args.start,
            end=args.end,
            hold_days=args.hold_days,
            capital_per_trade=args.capital,
        )

        tag = f"dividend_hold{args.hold_days}_{args.start}_to_{args.end}"
        out_csv = f"outputs/{tag}_trades.csv"
        trades_df.to_csv(out_csv, index=False)

        print(f"\nStrategy: dividend | Tickers: {', '.join(tickers)}")
        print(f"Saved CSV -> {out_csv}")

        if trades_df.empty:
            print("No trades found.")
        else:
            print(trades_df.head(20).to_string(index=False))

        return

    df = fetch_prices(args.ticker, args.start, args.end)
    close = df["close"].dropna()

    positions = regime_positions(
        close=close,
        lookback=args.lookback,
        down_days=args.down_days,
        up_days=args.up_days,
        crash_week_drop=args.crash_week_drop,
        crash_hold_days=args.crash_hold_days,
        crash_down_days=args.crash_down_days,
        crash_up_days=args.crash_up_days,
        down_leverage=args.down_leverage,
        disable_leverage_in_crash=(not args.allow_leverage_in_crash),
    )

    if args.debug:
        print("exposure value counts:\n", positions.value_counts(dropna=False).head(10))
        print("avg exposure:", float(positions.mean()))
        print("fraction invested:", float((positions > 0).mean()))
        print("max exposure:", float(positions.max()))

    res = run_backtest(close, positions, args.fee_bps)

    bh_rets = close.pct_change().fillna(0.0)
    bh_equity = (1.0 + bh_rets).cumprod()

    tag = (
        f"{args.ticker}_mom{args.lookback}"
        f"_d{args.down_days}_u{args.up_days}"
        f"_cr{int(args.crash_week_drop * 100)}w"
        f"_ch{args.crash_hold_days}"
        f"_cd{args.crash_down_days}_cu{args.crash_up_days}"
        f"_lev{args.down_leverage:.2f}"
        f"_{args.start}_to_{args.end}"
    )

    out_csv = f"outputs/{tag}_backtest.csv"
    out_plot = plot_equity(res.equity, bh_equity, tag)

    pd.DataFrame(
        {
            "close": close,
            "exposure": res.positions,
            "strategy_return": res.returns,
            "equity": res.equity,
        }
    ).to_csv(out_csv)

    print(f"\nStrategy: regime_positions | Ticker: {args.ticker}")
    print(f"Period: {close.index.min().date()} to {close.index.max().date()}")
    print(
        summary(res.equity, res.returns, res.positions).to_string(
            float_format=lambda x: f"{x:0.4f}" if isinstance(x, float) else str(x)
        )
    )

    print(f"\nSaved CSV -> {out_csv}")
    print(f"Saved plot -> {out_plot}")


if __name__ == "__main__":
    main()
