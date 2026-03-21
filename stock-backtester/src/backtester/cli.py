from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtester.strategies import regime_positions
from backtester.metrics import summary
from backtester.plot import plot_equity
from backtester.data import fetch_prices
from backtester.engines.position_engine import run_backtest


def main() -> None:
    p = argparse.ArgumentParser(description="Stock backtester (momentum regime + streak + crash trigger + leverage).")

    p.add_argument("--ticker", default="SPY")
    p.add_argument("--start", default="2005-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--fee-bps", type=float, default=2.0)

    # Momentum filter
    p.add_argument("--lookback", type=int, default=50, help="Lookback days for momentum filter (e.g., 50).")

    # Normal streak (used when mom <= 0 and not in crash mode)
    p.add_argument("--down-days", type=int, default=2, help="Buy after N down days in a row (when mom <= 0).")
    p.add_argument("--up-days", type=int, default=1, help="Sell after N up days in a row (when mom <= 0).")

    # Crash trigger (5 trading days ~ 1 week)
    p.add_argument("--crash-week-drop", type=float, default=0.08,
                   help="Trigger crash mode if 5-day return <= -this (e.g., 0.08 = -8%).")
    p.add_argument("--crash-hold-days", type=int, default=5,
                   help="Keep crash mode active for this many trading days after trigger.")
    p.add_argument("--crash-down-days", type=int, default=1,
                   help="Buy streak during crash mode (faster).")
    p.add_argument("--crash-up-days", type=int, default=1,
                   help="Sell streak during crash mode (faster).")

    # Leverage in mom<=0 regime
    p.add_argument("--down-leverage", type=float, default=1.3,
                   help="Exposure when mom <= 0 and long (e.g., 1.3 = 130% long).")
    p.add_argument("--allow-leverage-in-crash", action="store_true",
                   help="If set, leverage is also applied during crash mode (NOT recommended).")

    p.add_argument("--debug", action="store_true", help="Print sanity checks.")
    args = p.parse_args()

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

    # Buy & hold benchmark
    bh_rets = close.pct_change().fillna(0.0)
    bh_equity = (1.0 + bh_rets).cumprod()

    # Outputs (unique per run)
    Path("outputs").mkdir(exist_ok=True)
    tag = (
        f"{args.ticker}_mom{args.lookback}"
        f"_d{args.down_days}_u{args.up_days}"
        f"_cr{int(args.crash_week_drop*100)}w"
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

