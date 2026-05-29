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
from backtester.engines.options_overlay_engine import run_options_overlay
from backtester.engines.position_engine import run_backtest
from backtester.metrics import summary
from backtester.plot import plot_equity
from backtester.strategies import regime_positions
from backtester.utils.output import get_output_paths


def main() -> None:
    p = argparse.ArgumentParser(
        description="Stock backtester with regime, dividend, router, and options-overlay support."
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
        "--output-root",
        type=Path,
        default=Path("outputs"),
        help=(
            "Root folder for saved backtest outputs. "
            "Default: outputs. Example: outputs/experiments/extreme_only_router"
        ),
    )

    p.add_argument(
        "--use-regime-router",
        action="store_true",
        help="Use GARCH regime router to scale equity exposure.",
    )
    p.add_argument(
        "--use-options-overlay",
        action="store_true",
        help="Add simplified straddle/strangle options overlay returns.",
    )
    p.add_argument(
        "--options-overlay-tickers",
        nargs="+",
        default=None,
        help=(
            "Only apply the options overlay to these tickers. "
            "Example: --options-overlay-tickers NVDA TSLA. "
            "If omitted, --use-options-overlay applies to all tickers."
        ),
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

    options_overlay_tickers: set[str] | None = None
    if args.options_overlay_tickers is not None:
        options_overlay_tickers = {ticker.upper() for ticker in args.options_overlay_tickers}

    args.output_root.mkdir(parents=True, exist_ok=True)

    if args.strategy == "dividend":
        if not args.tickers:
            raise ValueError("--tickers is required when --strategy dividend is used.")

        tickers = [ticker.upper() for ticker in args.tickers]

        trades_df = run_dividend_strategy(
            tickers=tickers,
            start=args.start,
            end=args.end,
            hold_days=args.hold_days,
            capital_per_trade=args.capital,
        )

        summary_df = summarize_dividend_trades(trades_df)

        paths = get_output_paths("dividend", "multi", output_root=args.output_root)
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

    ticker = args.ticker.upper()

    allow_options_overlay_for_ticker = (
        args.use_options_overlay
        and (
            options_overlay_tickers is None
            or ticker in options_overlay_tickers
        )
    )

    df = fetch_prices(ticker, args.start, args.end)
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

    # We need GARCH routes when either the equity router is enabled or the
    # options overlay is actually allowed for this ticker.
    if args.use_regime_router or allow_options_overlay_for_ticker:
        garch_df = compute_garch_metrics(close)
        routes = add_regime_routes(garch_df)

    if args.use_regime_router:
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
        print("\n=== EQUITY EXPOSURE ===")
        print("exposure value counts:\n", positions.value_counts(dropna=False).head(15))
        print("avg exposure:", float(positions.mean()))
        print("fraction invested:", float((positions > 0).mean()))
        print("max exposure:", float(positions.max()))

        if args.use_options_overlay and not allow_options_overlay_for_ticker:
            allowed = (
                "ALL"
                if options_overlay_tickers is None
                else ", ".join(sorted(options_overlay_tickers))
            )
            print("\n=== OPTIONS OVERLAY SKIPPED ===")
            print(f"Ticker {ticker} is not in allowed overlay set: {allowed}")

    equity_res = run_backtest(close, positions, args.fee_bps)

    options_overlay = None
    options_returns = pd.Series(
        0.0, index=equity_res.returns.index, name="options_overlay_return"
    )

    if allow_options_overlay_for_ticker:
        options_overlay = run_options_overlay(close, routes=routes)

        options_returns = (
            options_overlay.returns.reindex(equity_res.returns.index)
            .fillna(0.0)
            .astype(float)
        )
        options_returns.name = "options_overlay_return"

        if args.debug:
            print("\n=== OPTIONS OVERLAY ENABLED ===")
            print("signal counts:")
            print(options_overlay.signals.value_counts())
            print("\nlatest options diagnostics:")
            print(
                options_overlay.diagnostics[
                    [
                        "fast_vol",
                        "slow_iv_proxy",
                        "regime_mean",
                        "options_signal",
                        "options_overlay_return",
                        "options_overlay_equity",
                    ]
                ].tail(10)
            )

    combined_returns = equity_res.returns.add(options_returns, fill_value=0.0)
    combined_returns.name = "combined_strategy_return"
    combined_equity = (1.0 + combined_returns).cumprod()
    combined_equity.name = "combined_equity"

    bh_rets = close.pct_change().fillna(0.0)
    bh_equity = (1.0 + bh_rets).cumprod()
    bh_equity.name = "buy_hold_equity"

    paths = get_output_paths("regime", ticker, output_root=args.output_root)
    out_plot = plot_equity(combined_equity, bh_equity, paths["plot"])

    output_df = pd.DataFrame(
        {
            "close": close,
            "exposure": equity_res.positions,
            "equity_strategy_return": equity_res.returns,
            "equity_strategy_equity": equity_res.equity,
            "options_overlay_return": options_returns,
            "combined_strategy_return": combined_returns,
            "combined_equity": combined_equity,
            "buy_hold_equity": bh_equity,
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

    if options_overlay is not None:
        option_cols = [
            "options_signal",
            "fast_vol",
            "slow_iv_proxy",
            "regime_mean",
            "options_overlay_equity",
        ]

        output_df = output_df.join(
            options_overlay.diagnostics[option_cols],
            how="left",
        )
    elif args.use_options_overlay:
        # Keep a useful column in skipped-overlay runs so comparison scripts can
        # still see that the overlay contributed nothing.
        output_df["options_signal"] = "SKIPPED"
        output_df["options_overlay_equity"] = 1.0

    output_df.to_csv(paths["data"])

    strategy_name = "regime_positions"
    if args.use_regime_router:
        strategy_name += " + regime_router"
    if allow_options_overlay_for_ticker:
        strategy_name += " + options_overlay"
    elif args.use_options_overlay and options_overlay_tickers is not None:
        strategy_name += " + options_overlay_skipped"

    print(f"\nStrategy: {strategy_name} | Ticker: {ticker}")
    print(f"Period: {close.index.min().date()} to {close.index.max().date()}")

    print("\n=== COMBINED PORTFOLIO SUMMARY ===")
    print(
        summary(combined_equity, combined_returns, equity_res.positions).to_string(
            float_format=lambda x: f"{x:0.4f}" if isinstance(x, float) else str(x)
        )
    )

    if args.use_options_overlay:
        print("\n=== EQUITY-ONLY SUMMARY ===")
        print(
            summary(
                equity_res.equity, equity_res.returns, equity_res.positions
            ).to_string(
                float_format=lambda x: f"{x:0.4f}" if isinstance(x, float) else str(x)
            )
        )

    print(f"\nSaved CSV -> {paths['data']}")
    print(f"Saved plot -> {out_plot}")


if __name__ == "__main__":
    main()
