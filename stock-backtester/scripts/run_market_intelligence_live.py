from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.batch import analyze_batch, load_price_risk_features, read_query_file
from backtester.intelligence.candidates import action_label, load_candidate_queries
from backtester.intelligence.price_risk import (
    PriceRiskRow,
    build_price_risk_features,
    download_prices,
    download_ticker_universe,
    load_peer_map,
    load_price_frame,
    write_price_risk_csv,
)
from backtester.intelligence.source_fetcher import (
    default_source_output_path,
    fetch_documents_for_queries,
    write_documents_jsonl,
)


DEFAULT_OUTPUT_DIR = Path("outputs/intelligence")
DEFAULT_PRICE_FEATURES = Path("data/intelligence/features/price_risk_features.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch sources, build price risk, and run Market Intelligence in one command."
    )
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--queries", nargs="+", help="Manual query list, e.g. PLTR QQQ MARKET.")
    query_group.add_argument("--query-file", type=Path, help="One query per line.")
    query_group.add_argument("--candidates", type=Path, help="CSV/parquet signal table to sweep.")

    price_group = parser.add_mutually_exclusive_group(required=True)
    price_group.add_argument("--download-prices", action="store_true", help="Download recent prices with yfinance.")
    price_group.add_argument("--prices", type=Path, help="Local CSV/parquet price file.")

    parser.add_argument("--top-n", type=int, default=50, help="Top candidates to sweep when --candidates is used.")
    parser.add_argument("--ticker-col", help="Ticker column for --candidates.")
    parser.add_argument("--date-col", help="Date column for --candidates.")
    parser.add_argument("--latest-date-only", action="store_true", help="Use only the newest signal date from --candidates.")
    parser.add_argument("--rank-col", help="Ranking column for --candidates.")
    parser.add_argument("--rank-ascending", action="store_true", help="Use if smaller rank values are better.")
    parser.add_argument("--benchmark", default="QQQ")
    parser.add_argument("--peer-map", type=Path, default=Path("data/intelligence/features/sample_peer_map.csv"))
    parser.add_argument("--download-period", default="6mo")
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--sources", nargs="+", default=["yfinance"], choices=["all", "yfinance", "yahoo", "google", "sec"])
    parser.add_argument("--max-items-per-source", type=int, default=8)
    parser.add_argument("--sources-out", type=Path)
    parser.add_argument("--price-features-out", type=Path, default=DEFAULT_PRICE_FEATURES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_OUTPUT_DIR / "intelligence_features.csv")
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_OUTPUT_DIR / "intelligence_batch_summary.csv")
    return parser.parse_args()


def normalize_sources(values: list[str]) -> set[str]:
    sources = {value.lower() for value in values}
    if "all" in sources:
        return {"yfinance", "yahoo", "google", "sec"}
    return sources


def resolve_queries(args: argparse.Namespace) -> list[str]:
    if args.queries is not None:
        return [query.strip().upper() for query in args.queries if query.strip()]
    if args.query_file is not None:
        return [query.strip().upper() for query in read_query_file(args.query_file) if query.strip()]
    rank_ascending = args.rank_ascending if args.rank_col else None
    return load_candidate_queries(
        args.candidates,
        top_n=args.top_n,
        ticker_col=args.ticker_col,
        rank_col=args.rank_col,
        rank_ascending=rank_ascending,
        date_col=args.date_col,
        latest_date_only=args.latest_date_only,
    )


def main() -> None:
    args = parse_args()
    queries = resolve_queries(args)
    if not queries:
        raise SystemExit("No queries resolved.")

    print(f"Queries: {', '.join(queries[:20])}" + (" ..." if len(queries) > 20 else ""))

    sources_out = args.sources_out or default_source_output_path()
    docs = fetch_documents_for_queries(
        queries,
        sources=normalize_sources(args.sources),
        max_items_per_source=args.max_items_per_source,
    )
    write_documents_jsonl(docs, sources_out)
    print(f"Saved sources: {sources_out} ({len(docs)} documents)")

    peer_map = load_peer_map(args.peer_map)
    if args.download_prices:
        tickers = download_ticker_universe(queries, benchmark=args.benchmark, peer_map=peer_map)
        prices = download_prices(tickers, period=args.download_period)
    else:
        prices = load_price_frame(args.prices)

    price_rows: list[PriceRiskRow] = build_price_risk_features(
        prices,
        queries,
        benchmark=args.benchmark,
        peer_map=peer_map,
        lookback=args.lookback,
    )
    write_price_risk_csv(price_rows, args.price_features_out)
    print(f"Saved price features: {args.price_features_out}")

    run_id, reports = analyze_batch(
        queries=queries,
        documents=docs,
        output_dir=args.output_dir,
        features_csv=args.features_csv,
        summary_csv=args.summary_csv,
        price_features=load_price_risk_features(args.price_features_out),
    )

    print(f"Run id: {run_id}")
    for report in sorted(reports, key=lambda r: r.regime_break_score, reverse=True)[: min(25, len(reports))]:
        print(
            f"{report.query}: break={report.regime_break_score:.4f} "
            f"sentiment={report.sentiment_score:.4f} "
            f"confidence={report.confidence:.4f} "
            f"action={action_label(report.regime_break_score)}"
        )


if __name__ == "__main__":
    main()
