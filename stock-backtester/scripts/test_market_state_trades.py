from __future__ import annotations

import argparse
from pathlib import Path

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


def compute_raw_momentum_score(prices: pd.DataFrame) -> float:
    """
    Simple placeholder alpha score.

    This is NOT the final strategy scorecard.
    It is only here so the market-state system can produce paper trades.

    Uses:
    - 21-day return
    - 63-day return

    Positive momentum gets a positive score.
    Negative momentum becomes zero.
    """
    close = prices["close"].dropna()

    if len(close) < 70:
        return 0.0

    ret_21 = close.iloc[-1] / close.iloc[-22] - 1.0
    ret_63 = close.iloc[-1] / close.iloc[-64] - 1.0

    raw_score = (0.40 * ret_21) + (0.60 * ret_63)

    return float(max(raw_score, 0.0))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate paper trades using MarketState + simple momentum scores."
    )

    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        default=["SPY", "QQQ", "NVDA", "JPM", "XOM"],
        help="Ticker symbols to evaluate.",
    )

    parser.add_argument(
        "--start",
        default="2018-01-01",
        help="Start date. Default: 2018-01-01",
    )

    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date. Default: latest available data.",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=10_000.0,
        help="Starting cash capital. Default: 10000",
    )

    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.35,
        help="Maximum target weight per ticker. Default: 0.35",
    )

    parser.add_argument(
        "--min-trade-dollars",
        type=float,
        default=50.0,
        help="Minimum trade size in dollars. Default: 50",
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
        help="Rolling z-score / percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of bins for return entropy. Default: 10",
    )

    parser.add_argument(
        "--output",
        default="outputs/trades/market_state_trade_plan.csv",
        help="CSV output path.",
    )

    return parser.parse_args()


def analyze_one_ticker(
    ticker: str,
    start: str,
    end: str | None,
    entropy_config: EntropyConfig,
) -> dict:
    compute_garch_metrics = import_compute_garch_metrics()

    df = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    prices = clean_yfinance_columns(df)

    if "close" not in prices.columns:
        raise ValueError(f"{ticker}: missing close column. Got {list(prices.columns)}")

    latest_close = float(prices["close"].dropna().iloc[-1])

    vol_price_series = prices[["close"]].copy()
    vol_metrics = compute_garch_metrics(vol_price_series)

    if vol_metrics.empty:
        raise ValueError(f"{ticker}: volatility metrics returned empty DataFrame.")

    latest_vol_row = vol_metrics.dropna().iloc[-1]
    volatility_decision = make_volatility_decision(latest_vol_row)

    entropy_metrics = compute_entropy_metrics(prices, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)
    entropy_decision = latest_entropy_decision(entropy_metrics)

    market_state = build_market_state(
        entropy_decision=entropy_decision,
        volatility_decision=volatility_decision,
    )

    raw_score = compute_raw_momentum_score(prices)

    if not market_state.allow_new_equity_positions:
        adjusted_score = 0.0
        block_reason = "equity_blocked_by_market_state"
    else:
        adjusted_score = raw_score * market_state.combined_multiplier
        block_reason = ""

    return {
        "ticker": ticker,
        "close": latest_close,
        "raw_score": raw_score,
        "adjusted_score": adjusted_score,
        "vol_regime": volatility_decision.vol_regime,
        "return_entropy_regime": entropy_decision.entropy_regime,
        "direction_entropy_regime": entropy_decision.direction_entropy_regime,
        "entropy_state": entropy_decision.entropy_state,
        "risk_multiplier": market_state.risk_multiplier,
        "signal_trust_multiplier": market_state.signal_trust_multiplier,
        "combined_multiplier": market_state.combined_multiplier,
        "allow_new_equity_positions": market_state.allow_new_equity_positions,
        "allow_options": market_state.allow_options,
        "capital_posture": market_state.capital_posture,
        "preferred_strategy": market_state.preferred_strategy,
        "block_reason": block_reason,
        "market_state_reason": market_state.reason,
        "error": None,
    }


def assign_target_weights(
    result: pd.DataFrame,
    max_weight: float,
) -> pd.DataFrame:
    out = result.copy()

    out["target_weight"] = 0.0

    if "error" in out.columns:
        valid_mask = out["error"].isna()
    else:
        valid_mask = pd.Series(True, index=out.index)

    allowed_mask = (
        valid_mask & out["allow_new_equity_positions"] & (out["adjusted_score"] > 0)
    )

    allowed = out.loc[allowed_mask].copy()

    if allowed.empty:
        return out

    score_sum = allowed["adjusted_score"].sum()

    if score_sum <= 0:
        return out

    # Preserve some cash when the market-state system is cautious.
    # If all candidates are healthy, gross exposure approaches 100%.
    target_gross_exposure = float(
        np.clip(allowed["combined_multiplier"].mean(), 0.0, 1.0)
    )

    raw_weights = (allowed["adjusted_score"] / score_sum) * target_gross_exposure

    capped_weights = raw_weights.clip(upper=max_weight)

    out.loc[allowed.index, "target_weight"] = capped_weights

    return out


def build_trade_plan(
    result: pd.DataFrame,
    capital: float,
    min_trade_dollars: float,
) -> pd.DataFrame:
    out = result.copy()

    out["target_dollars"] = out["target_weight"] * capital
    out["shares"] = np.floor(out["target_dollars"] / out["close"]).fillna(0).astype(int)
    out["trade_dollars"] = out["shares"] * out["close"]

    out["cash_left_from_rounding"] = out["target_dollars"] - out["trade_dollars"]

    def decide_action(row: pd.Series) -> str:
        if pd.notna(row.get("error")):
            return "ERROR"

        if not bool(row.get("allow_new_equity_positions", False)):
            return "BLOCK"

        if row.get("adjusted_score", 0.0) <= 0:
            return "SKIP"

        if row.get("trade_dollars", 0.0) < min_trade_dollars:
            return "SKIP"

        if row.get("shares", 0) <= 0:
            return "SKIP"

        return "BUY"

    out["action"] = out.apply(decide_action, axis=1)

    return out


def _yn(value) -> str:
    if pd.isna(value):
        return "?"
    return "Y" if bool(value) else "N"


def print_trade_plan(plan: pd.DataFrame, capital: float) -> None:
    display = plan.copy()

    numeric_cols = [
        "close",
        "raw_score",
        "adjusted_score",
        "risk_multiplier",
        "signal_trust_multiplier",
        "combined_multiplier",
        "target_weight",
        "target_dollars",
        "trade_dollars",
    ]

    for col in numeric_cols:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce").round(4)

    if "target_weight" in display.columns:
        display["target_weight"] = (display["target_weight"] * 100).round(2)

    if "allow_new_equity_positions" in display.columns:
        display["allow_new_equity_positions"] = display[
            "allow_new_equity_positions"
        ].apply(_yn)

    if "allow_options" in display.columns:
        display["allow_options"] = display["allow_options"].apply(_yn)

    rename_map = {
        "ticker": "Ticker",
        "close": "Close",
        "vol_regime": "Vol",
        "return_entropy_regime": "RetEnt",
        "direction_entropy_regime": "DirEnt",
        "raw_score": "Raw",
        "adjusted_score": "Adj",
        "combined_multiplier": "Combo",
        "target_weight": "Wt%",
        "target_dollars": "Target$",
        "shares": "Shares",
        "trade_dollars": "Trade$",
        "allow_new_equity_positions": "Eq",
        "allow_options": "Opt",
        "capital_posture": "Posture",
        "action": "Action",
    }

    display = display.rename(columns=rename_map)

    terminal_cols = [
        "Ticker",
        "Close",
        "Vol",
        "RetEnt",
        "DirEnt",
        "Raw",
        "Adj",
        "Combo",
        "Eq",
        "Opt",
        "Posture",
        "Wt%",
        "Target$",
        "Shares",
        "Trade$",
        "Action",
    ]

    terminal_cols = [col for col in terminal_cols if col in display.columns]

    action_rank = {
        "BUY": 0,
        "BLOCK": 1,
        "SKIP": 2,
        "ERROR": 3,
    }

    display["_rank"] = display["Action"].map(action_rank).fillna(99)
    display = display.sort_values(
        ["_rank", "Wt%", "Ticker"], ascending=[True, False, True]
    )
    display = display.drop(columns=["_rank"])

    print("\nPaper Trade Plan:")
    print(
        tabulate(
            display[terminal_cols], headers="keys", tablefmt="github", showindex=False
        )
    )

    total_trade_dollars = plan.loc[plan["action"] == "BUY", "trade_dollars"].sum()
    cash_remaining = capital - total_trade_dollars

    print("\nTrade Summary:")
    print(f"  Starting capital: ${capital:,.2f}")
    print(f"  Planned buys:     ${total_trade_dollars:,.2f}")
    print(f"  Cash remaining:   ${cash_remaining:,.2f}")

    action_counts = plan["action"].value_counts()
    print("\nAction Breakdown:")
    for action, count in action_counts.items():
        print(f"  {action}: {count}")


def main() -> None:
    args = parse_args()

    tickers = [ticker.upper() for ticker in args.tickers]

    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    rows = []

    print("\nGenerating paper trade plan for tickers:")
    print(", ".join(tickers))
    print(f"Capital: ${args.capital:,.2f}")

    for ticker in tickers:
        print(f"Scanning {ticker}...")

        try:
            row = analyze_one_ticker(
                ticker=ticker,
                start=args.start,
                end=args.end,
                entropy_config=entropy_config,
            )
            rows.append(row)
        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "error": str(exc),
                    "close": np.nan,
                    "raw_score": 0.0,
                    "adjusted_score": 0.0,
                    "target_weight": 0.0,
                }
            )
            print(f"  {ticker} failed: {exc}")

    result = pd.DataFrame(rows)

    result = assign_target_weights(
        result,
        max_weight=args.max_weight,
    )

    plan = build_trade_plan(
        result,
        capital=args.capital,
        min_trade_dollars=args.min_trade_dollars,
    )

    print_trade_plan(plan, capital=args.capital)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(output_path, index=False)

    print(f"\nSaved full trade plan to: {output_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
