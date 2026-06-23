from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.batch import (
    PriceRiskFeatures,
    analyze_batch,
    load_price_risk_features,
    read_query_file,
)
from backtester.intelligence.source_loader import load_jsonl


DEFAULT_OUTPUT_DIR = Path("outputs/intelligence")
DEFAULT_FEATURES_CSV = DEFAULT_OUTPUT_DIR / "intelligence_features.csv"
DEFAULT_SUMMARY_CSV = DEFAULT_OUTPUT_DIR / "intelligence_batch_summary.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Market Intelligence for multiple tickers/indexes/topics."
    )
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "--queries",
        nargs="+",
        help="Queries to analyze, e.g. --queries PLTR QQQ MARKET.",
    )
    query_group.add_argument(
        "--query-file",
        type=Path,
        help="Text file containing one query per line. Blank lines and # comments are ignored.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Trusted source JSONL file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument(
        "--price-features-csv",
        type=Path,
        help="Optional CSV with query,peer_divergence,volume_shock,trend_damage columns.",
    )
    parser.add_argument("--default-peer-divergence", type=float, default=0.0)
    parser.add_argument("--default-volume-shock", type=float, default=0.0)
    parser.add_argument("--default-trend-damage", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = args.queries if args.queries is not None else read_query_file(args.query_file)
    queries = [query.strip().upper() for query in queries if query.strip()]
    if not queries:
        raise SystemExit("No queries provided.")

    docs = load_jsonl(args.input)
    price_features = load_price_risk_features(args.price_features_csv)
    default_price_features = PriceRiskFeatures(
        peer_divergence=args.default_peer_divergence,
        volume_shock=args.default_volume_shock,
        trend_damage=args.default_trend_damage,
    )

    run_id, reports = analyze_batch(
        queries=queries,
        documents=docs,
        output_dir=args.output_dir,
        features_csv=args.features_csv,
        summary_csv=args.summary_csv,
        price_features=price_features,
        default_price_features=default_price_features,
    )

    print(f"Run id: {run_id}")
    for report in reports:
        print(
            f"{report.query}: sentiment={report.sentiment_score:.4f} "
            f"break={report.regime_break_score:.4f} "
            f"confidence={report.confidence:.4f} "
            f"pressure={report.dominant_pressure}"
        )
    print(f"Saved reports under: {args.output_dir / run_id}")
    print(f"Appended features: {args.features_csv}")
    print(f"Appended batch summary: {args.summary_csv}")


if __name__ == "__main__":
    main()
