from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtester.analytics.volatility import compute_garch_metrics
from backtester.data import fetch_prices
from backtester.decision.position_sizing import apply_route_risk_scaling
from backtester.decision.regime_router import add_regime_routes
from backtester.engines.event_engine import (
    run_dividend_strategy,
    summarize_dividend_trades,
)
from backtester.engines.position_engine import run_backtest
from backtester.metrics import summary
from backtester.plot import plot_equity
from backtester.strategies import regime_positions
from backtester.utils.output import get_output_paths


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

    p.add_argument(
        "--use-regime-router",
        action="store_true",
        help="Use GARCH regime router to scale position exposure.",
    )

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

        summary_df = summarize_dividend_trades(trades_df)

        paths = get_output_paths("dividend", "multi")
        trades_df.to_csv(paths["trades"], index=False)

        print(f"\nStrategy: dividend | Tickers: {', '.join(tickers)}")

        if not summary_df.empty:
            print("\n=== SUMMARY ===")
            print(
                summary_df.to_string(
                    index=False,
                    float_format=lambda x: (
                        f"{x:0.4f}" if isinstance(x, float) else str(x)
                    ),
                )
            )

        print(f"\nSaved CSV -> {paths['trades']}")

        if trades_df.empty:
            print("No trades found.")
        else:
            print("\n=== FIRST 20 TRADES ===")
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

    routes = None

    if args.use_regime_router:
        garch_df = compute_garch_metrics(close)
        routes = add_regime_routes(garch_df)

        positions = apply_route_risk_scaling(
            positions=positions,
            routes=routes,
        )

        if args.debug:
            print("\n=== REGIME ROUTER ENABLED ===")
            print(
                routes[
                    [
                        "active_regime",
                        "route_risk_multiplier",
                        "route_preferred_strategy",
                        "route_allow_options",
                        "route_allow_new_equity_positions",
                    ]
                ].tail(10)
            )

    if args.debug:
        print("exposure value counts:\n", positions.value_counts(dropna=False).head(10))
        print("avg exposure:", float(positions.mean()))
        print("fraction invested:", float((positions > 0).mean()))
        print("max exposure:", float(positions.max()))

    res = run_backtest(close, positions, args.fee_bps)

    bh_rets = close.pct_change().fillna(0.0)
    bh_equity = (1.0 + bh_rets).cumprod()

    route_tag = "_router" if args.use_regime_router else ""

    tag = (
        f"{args.ticker}_mom{args.lookback}"
        f"_d{args.down_days}_u{args.up_days}"
        f"_cr{int(args.crash_week_drop * 100)}w"
        f"_ch{args.crash_hold_days}"
        f"_cd{args.crash_down_days}_cu{args.crash_up_days}"
        f"_lev{args.down_leverage:.2f}"
        f"{route_tag}"
        f"_{args.start}_to_{args.end}"
    )

    paths = get_output_paths("regime", args.ticker)
    out_plot = plot_equity(res.equity, bh_equity, paths["plot"])

    output_df = pd.DataFrame(
        {
            "close": close,
            "exposure": res.positions,
            "strategy_return": res.returns,
            "equity": res.equity,
        }
    )

    if routes is not None:
        route_cols = [
            "active_regime",
            "route_risk_multiplier",
            "route_preferred_strategy",
            "route_allow_options",
            "route_allow_new_equity_positions",
        ]

        output_df = output_df.join(routes[route_cols], how="left")

    output_df.to_csv(paths["data"])

    strategy_name = "regime_positions"
    if args.use_regime_router:
        strategy_name += " + regime_router"

    print(f"\nStrategy: {strategy_name} | Ticker: {args.ticker}")
    print(f"Period: {close.index.min().date()} to {close.index.max().date()}")
    print(
        summary(res.equity, res.returns, res.positions).to_string(
            float_format=lambda x: f"{x:0.4f}" if isinstance(x, float) else str(x)
        )
    )
    print(f"\nSaved CSV -> {paths['data']}")
    print(f"Saved plot -> {out_plot}")


if __name__ == "__main__":
    main()
