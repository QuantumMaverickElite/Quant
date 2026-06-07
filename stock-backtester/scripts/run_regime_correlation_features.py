# scripts/run_regime_correlation_features.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtester.correlation import (
    RegimeCorrelationConfig,
    compute_rolling_regime_pair_correlations,
    prices_to_return_matrix,
    summarize_latest_market_compression,
    summarize_market_correlation_deformation,
    summarize_regime_pair_correlations,
    summarize_ticker_stress_sensitivity,
)


def load_universe(path: str | Path) -> list[str]:
    universe_path = Path(path)

    if not universe_path.exists():
        raise FileNotFoundError(f"Universe file not found: {universe_path}")

    tickers: list[str] = []

    for line in universe_path.read_text().splitlines():
        clean = line.strip()

        if not clean:
            continue

        if clean.startswith("#"):
            continue

        tickers.append(clean.upper())

    if not tickers:
        raise ValueError(f"Universe file is empty: {universe_path}")

    return list(dict.fromkeys(tickers))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build regime-conditioned pair correlation features."
    )

    parser.add_argument(
        "--universe-file",
        default="data/universes/liquid_large_mid.txt",
        help="Ticker universe file. Used when --tickers is not supplied.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Optional explicit ticker list. Overrides --universe-file.",
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)

    parser.add_argument("--window", type=int, default=120)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--backend", choices=["numpy", "cupy"], default="numpy")

    parser.add_argument(
        "--context",
        default="outputs/context/market_context.parquet",
        help="Market context parquet with volatility_state / entropy_state.",
    )
    parser.add_argument(
        "--regime-column",
        default="volatility_state",
        help="Column in market context used as the regime label.",
    )

    parser.add_argument(
        "--pair-out",
        default="outputs/correlation/regime_pair_correlations.parquet",
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/correlation/regime_correlation_summary.csv",
    )
    parser.add_argument(
        "--ticker-out",
        default="outputs/correlation/regime_ticker_stress_sensitivity.csv",
    )
    parser.add_argument(
        "--latest-out",
        default="outputs/correlation/regime_correlation_latest.csv",
    )
    parser.add_argument(
        "--market-out", default="outputs/correlation/regime_market_deformation.csv"
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


def main() -> None:
    args = parse_args()

    if args.tickers is not None:
        tickers = [ticker.upper() for ticker in args.tickers]
    else:
        tickers = load_universe(args.universe_file)

    tickers = list(dict.fromkeys(tickers))

    print(f"Using {len(tickers):,} tickers")
    print(tickers[:25], "..." if len(tickers) > 25 else "")

    prices = download_adjusted_close(
        tickers=tickers,
        start=args.start,
        end=args.end,
    )

    return_matrix = prices_to_return_matrix(
        prices,
        tickers=tickers,
        min_non_nan_fraction=0.85,
    )

    market_context = pd.read_parquet(args.context)

    config = RegimeCorrelationConfig(
        window=args.window,
        step=args.step,
        backend=args.backend,
        regime_column=args.regime_column,
    )

    pair_corr = compute_rolling_regime_pair_correlations(
        return_matrix=return_matrix,
        market_context=market_context,
        config=config,
    )

    summary = summarize_regime_pair_correlations(pair_corr, config)
    ticker_summary = summarize_ticker_stress_sensitivity(summary)
    latest = summarize_latest_market_compression(pair_corr, summary)
    market_deformation = summarize_market_correlation_deformation(pair_corr, summary)

    for path in [
        args.pair_out,
        args.summary_out,
        args.ticker_out,
        args.latest_out,
        args.market_out,
    ]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    pair_corr.to_parquet(args.pair_out, index=False)
    summary.to_csv(args.summary_out, index=False)
    ticker_summary.to_csv(args.ticker_out, index=False)
    latest.to_csv(args.latest_out, index=False)
    market_deformation.to_csv(args.market_out, index=False)

    print(f"Saved pair correlations: {len(pair_corr):,} rows -> {args.pair_out}")
    print(f"Saved pair summary:      {len(summary):,} rows -> {args.summary_out}")
    print(f"Saved ticker summary:    {len(ticker_summary):,} rows -> {args.ticker_out}")
    print(f"Saved latest summary:    {len(latest):,} rows -> {args.latest_out}")
    print(
        f"Saved market deformation: {len(market_deformation):,} rows -> {args.market_out}"
    )

    print("\nRegime counts:")
    if not pair_corr.empty:
        print(pair_corr[["date", "regime"]].drop_duplicates()["regime"].value_counts())

    print("\nTop diversification failures:")
    print(summary.head(20).to_string(index=False))

    print("\nMost stress-sensitive tickers:")
    print(ticker_summary.head(20).to_string(index=False))

    print("\nLatest compression:")
    print(latest.to_string(index=False))

    print("\nMarket deformation tail:")
    print(market_deformation.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
