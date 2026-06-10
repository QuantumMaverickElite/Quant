from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import yfinance as yf


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build market-cap cache for tickers appearing in a signal file."
    )

    p.add_argument(
        "--signals",
        required=True,
        help="Signal parquet containing ticker column.",
    )
    p.add_argument(
        "--out",
        default="outputs/cache/market_caps/market_caps_from_signals.csv",
        help="Output market-cap cache CSV.",
    )
    p.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.25,
        help="Sleep between ticker requests.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max tickers for smoke tests.",
    )

    return p.parse_args()


def normalize_ticker(ticker: object) -> str:
    return str(ticker).upper().strip().replace(".", "-")


def fetch_market_cap(ticker: str) -> float | None:
    try:
        yt = yf.Ticker(ticker)

        # fast_info is quicker when available.
        fast_info = getattr(yt, "fast_info", None)
        if fast_info is not None:
            market_cap = fast_info.get("market_cap")
            if market_cap is not None and pd.notna(market_cap):
                return float(market_cap)

        info = yt.get_info()
        market_cap = info.get("marketCap")
        if market_cap is not None and pd.notna(market_cap):
            return float(market_cap)

    except Exception as e:
        print(f"WARNING: failed {ticker}: {e}")

    return None


def main() -> None:
    args = parse_args()

    signals = pd.read_parquet(args.signals)

    if "ticker" not in signals.columns:
        raise ValueError("Signal file must contain ticker column.")

    tickers = sorted({normalize_ticker(t) for t in signals["ticker"].dropna()})

    if args.limit is not None:
        tickers = tickers[: args.limit]

    rows = []

    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i}/{len(tickers)}] {ticker}")

        market_cap = fetch_market_cap(ticker)

        rows.append(
            {
                "ticker": ticker,
                "market_cap": market_cap,
                "market_cap_source": "yfinance",
            }
        )

        time.sleep(args.sleep_seconds)

    out = pd.DataFrame(rows)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print()
    print(f"Saved market-cap cache: {out_path}")
    print(f"Rows: {len(out):,}")
    print(f"Missing market caps: {out['market_cap'].isna().sum():,}")
    print()
    print(out.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
