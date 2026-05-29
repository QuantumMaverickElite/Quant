from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse

import pandas as pd
import yfinance as yf

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.decision.entropy_decision import (
    apply_entropy_decision_columns,
    latest_entropy_decision,
)
from backtester.decision.market_state import build_market_state


@dataclass(frozen=True)
class MockVolatilityDecision:
    volatility_regime: str
    risk_multiplier: float
    allow_new_equity_positions: bool
    allow_options: bool
    preferred_strategy: str | None = None


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test combined MarketState using entropy plus mock volatility."
    )

    parser.add_argument(
        "--ticker",
        "-t",
        default="SPY",
        help="Ticker symbol to analyze. Default: SPY",
    )

    parser.add_argument(
        "--start",
        default="2018-01-01",
        help="Start date. Default: 2018-01-01",
    )

    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date. Default: latest available data",
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
        "--vol-regime",
        default="NORMAL",
        choices=["LOW", "NORMAL", "HIGH", "EXTREME", "UNKNOWN"],
        help="Mock volatility regime. Default: NORMAL",
    )

    parser.add_argument(
        "--risk-multiplier",
        type=float,
        default=1.0,
        help="Mock volatility risk multiplier. Default: 1.0",
    )

    parser.add_argument(
        "--block-equity",
        action="store_true",
        help="Mock volatility gate blocks new equity positions.",
    )

    parser.add_argument(
        "--allow-options",
        action="store_true",
        help="Mock volatility decision allows options overlay.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticker = args.ticker.upper()

    print(f"\nRunning MarketState test for {ticker}")
    print(f"Mock volatility regime: {args.vol_regime}")
    print(f"Mock risk multiplier: {args.risk_multiplier:.2f}")

    df = yf.download(
        ticker,
        start=args.start,
        end=args.end,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    df = clean_yfinance_columns(df)

    if "close" not in df.columns:
        raise ValueError(f"Missing close column. Got columns: {list(df.columns)}")

    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    metrics = compute_entropy_metrics(df, entropy_config)
    metrics = apply_entropy_decision_columns(metrics)

    entropy_decision = latest_entropy_decision(metrics)

    volatility_decision = MockVolatilityDecision(
        volatility_regime=args.vol_regime,
        risk_multiplier=args.risk_multiplier,
        allow_new_equity_positions=not args.block_equity,
        allow_options=args.allow_options,
        preferred_strategy=None,
    )

    market_state = build_market_state(
        entropy_decision=entropy_decision,
        volatility_decision=volatility_decision,
    )

    print("\nEntropy decision:")
    print(entropy_decision)

    print("\nEntropy state description:")
    print(entropy_decision.entropy_state_description)

    print("\nMarket state:")
    print(market_state)

    print("\nMarket state reason:")
    print(market_state.reason)

    print("\nTail:")
    cols = [
        "close",
        "entropy_regime",
        "direction_entropy_regime",
        "entropy_state",
        "signal_trust_multiplier",
    ]
    print(metrics[cols].tail(10))

    print("\nDone.")


if __name__ == "__main__":
    main()
