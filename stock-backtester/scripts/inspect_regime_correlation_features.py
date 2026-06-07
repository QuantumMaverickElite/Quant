# scripts/inspect_regime_correlation_features.py

from __future__ import annotations

import argparse

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect regime-conditioned correlation outputs."
    )

    parser.add_argument(
        "--summary",
        default="outputs/correlation/regime_correlation_summary.csv",
    )
    parser.add_argument(
        "--ticker",
        default="outputs/correlation/regime_ticker_stress_sensitivity.csv",
    )
    parser.add_argument(
        "--latest",
        default="outputs/correlation/regime_correlation_latest.csv",
    )
    parser.add_argument("--top-n", type=int, default=25)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    summary = pd.read_csv(args.summary)
    ticker = pd.read_csv(args.ticker)
    latest = pd.read_csv(args.latest)

    print("\n" + "=" * 90)
    print("LATEST MARKET CORRELATION DEFORMATION")
    print("=" * 90)
    print(latest.to_string(index=False))

    print("\n" + "=" * 90)
    print("TOP COMPRESSION PAIRS")
    print("=" * 90)
    compression_cols = [
        "ticker_a",
        "ticker_b",
        "avg_corr_calm",
        "avg_corr_stress",
        "stress_corr_delta",
        "stress_corr_delta_z",
        "diversification_failure_label",
        "compression_rank",
    ]
    print(
        summary.sort_values("stress_corr_delta", ascending=False)
        .head(args.top_n)[compression_cols]
        .to_string(index=False)
    )

    print("\n" + "=" * 90)
    print("TOP FRAGMENTATION PAIRS")
    print("=" * 90)
    print(
        summary.sort_values("stress_corr_delta", ascending=True)
        .head(args.top_n)[compression_cols]
        .to_string(index=False)
    )

    print("\n" + "=" * 90)
    print("MOST STRESS-SENSITIVE TICKERS")
    print("=" * 90)
    print(ticker.head(args.top_n).to_string(index=False))

    print("\n" + "=" * 90)
    print("LEAST / NEGATIVELY STRESS-SENSITIVE TICKERS")
    print("=" * 90)
    print(
        ticker.sort_values("ticker_stress_sensitivity", ascending=True)
        .head(args.top_n)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
