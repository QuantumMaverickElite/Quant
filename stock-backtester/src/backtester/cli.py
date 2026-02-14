from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from backtester.metrics import summary
from backtester.plot import plot_equity


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series  # exposure: 0.0, 1.0, 1.3, etc.


def fetch_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [c.lower().strip() for c in df.columns]
    if "close" not in df.columns:
        raise ValueError(f"Available columns: {list(df.columns)}")

    return df


def regime_positions(
    close: pd.Series,
    lookback: int,
    down_days: int,
    up_days: int,
    crash_week_drop: float,
    crash_hold_days: int,
    crash_down_days: int,
    crash_up_days: int,
    down_leverage: float,
    disable_leverage_in_crash: bool = True,
) -> pd.Series:
    """
    Multi-regime strategy:

    1) Momentum override:
       - mom(t) = close(t)/close(t-lookback) - 1
       - if mom(t) > 0 -> hold long (exposure = 1.0)

    2) Otherwise (mom <= 0):
       - run streak mean-reversion:
         * enter long after `down_days` consecutive down days
         * exit to cash after `up_days` consecutive up days
       - when long, apply leverage in this regime: exposure = down_leverage (e.g. 1.3)

    3) Crash trigger:
       - week_ret(t) = close(t)/close(t-5) - 1
       - if week_ret(t) <= -crash_week_drop, then starting NEXT day, enable crash mode for `crash_hold_days` days
       - during crash mode:
         * ignore momentum override (no forced holding)
         * use faster streak params (crash_down_days / crash_up_days)
         * optionally disable leverage (default True) to avoid levering into panic

    We shift the final exposure series by 1 day to avoid lookahead.
    """

    mom = close / close.shift(lookback) - 1.0
    rets = close.pct_change()

    week_ret = close / close.shift(5) - 1.0
    crash_trigger_next = (week_ret <= -crash_week_drop).shift(1).fillna(False)
    crash_active = crash_trigger_next.rolling(crash_hold_days).max().fillna(0).astype(bool)

    exposure = pd.Series(0.0, index=close.index, dtype=float)

    in_pos = 0  # 0 or 1 (state), exposure is computed from state + regime
    down_streak = 0
    up_streak = 0

    for i in range(1, len(close)):
        in_crash = bool(crash_active.iloc[i])

        # regime flags
        mom_is_pos = pd.notna(mom.iloc[i]) and mom.iloc[i] > 0

        # Decide whether to force-hold (only when not in crash)
        if (not in_crash) and mom_is_pos:
            in_pos = 1
            down_streak = 0
            up_streak = 0
            exposure.iloc[i] = 1.0  # no leverage in momentum-up regime
            continue

        # pick streak params (normal vs crash)
        dd = crash_down_days if in_crash else down_days
        ud = crash_up_days if in_crash else up_days

        r = rets.iloc[i]
        if pd.isna(r):
            # keep previous state/exposure
            lev = 1.0
            if not mom_is_pos:
                lev = float(down_leverage)
                if disable_leverage_in_crash and in_crash:
                    lev = 1.0
            exposure.iloc[i] = lev * in_pos
            continue

        # update streak counters
        if r < 0:
            down_streak += 1
            up_streak = 0
        elif r > 0:
            up_streak += 1
            down_streak = 0
        else:
            down_streak = 0
            up_streak = 0

        # update state
        if in_pos == 0 and down_streak >= dd:
            in_pos = 1
        elif in_pos == 1 and up_streak >= ud:
            in_pos = 0

        # compute exposure from state + regime
        lev = 1.0
        if not mom_is_pos:
            lev = float(down_leverage)
            if disable_leverage_in_crash and in_crash:
                lev = 1.0

        exposure.iloc[i] = lev * in_pos

    return exposure.shift(1).fillna(0.0).astype(float)


def run_backtest(close: pd.Series, positions: pd.Series, fee_bps: float) -> BacktestResult:
    rets = close.pct_change().fillna(0.0)

    # Fee charged when exposure changes (enter/exit/resize)
    trades = positions.diff().abs().fillna(0.0)
    fee = (fee_bps / 10_000.0) * trades

    strat_rets = positions * rets - fee
    equity = (1.0 + strat_rets).cumprod()

    return BacktestResult(equity=equity, returns=strat_rets, positions=positions)


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

