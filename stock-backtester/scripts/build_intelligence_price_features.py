from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.batch import read_query_file
from backtester.intelligence.price_risk import (
    build_price_risk_features,
    download_ticker_universe,
    download_prices,
    load_peer_map,
    load_price_frame,
    write_price_risk_csv,
)


DEFAULT_OUTPUT = Path("data/intelligence/features/price_risk_features.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build price-derived risk features for the Market Intelligence Engine."
    )
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--queries", nargs="+", help="Tickers/topics to score, e.g. PLTR QQQ MARKET.")
    query_group.add_argument("--query-file", type=Path, help="One query per line.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--prices", type=Path, help="Local CSV/parquet price file.")
    source_group.add_argument("--download", action="store_true", help="Download recent OHLCV with yfinance.")
    parser.add_argument("--download-period", default="6mo", help="yfinance period. Default: 6mo.")
    parser.add_argument("--benchmark", default="QQQ", help="Benchmark ticker. Default: QQQ.")
    parser.add_argument("--peer-map", type=Path, help="Optional CSV with query,peer or query,peers columns.")
    parser.add_argument("--lookback", type=int, default=20, help="Return lookback in trading days. Default: 20.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = args.queries if args.queries is not None else read_query_file(args.query_file)
    queries = [query.strip().upper() for query in queries if query.strip()]
    if not queries:
        raise SystemExit("No queries provided.")

    peer_map = load_peer_map(args.peer_map)
    tickers = download_ticker_universe(queries, benchmark=args.benchmark, peer_map=peer_map)

    if args.download:
        prices = download_prices(tickers, period=args.download_period)
    else:
        prices = load_price_frame(args.prices)

    rows = build_price_risk_features(
        prices,
        queries,
        benchmark=args.benchmark,
        peer_map=peer_map,
        lookback=args.lookback,
    )
    write_price_risk_csv(rows, args.out)

    print(f"Saved price risk features: {args.out}")
    for row in rows:
        print(
            f"{row.query}: peer_divergence={row.peer_divergence:.4f} "
            f"volume_shock={row.volume_shock:.4f} trend_damage={row.trend_damage:.4f} "
            f"return={row.recent_return:.4f} benchmark={row.benchmark_return:.4f}"
        )


if __name__ == "__main__":
    main()
