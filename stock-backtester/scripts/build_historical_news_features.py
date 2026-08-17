from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.features.historical_news_feature_builder import (
    DEFAULT_WINDOWS,
    build_and_save_news_features,
    join_news_features_to_signals,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build point-in-time historical news and analyst features.")
    parser.add_argument("--news-sources", required=True, type=Path)
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--features-out", required=True, type=Path)
    parser.add_argument("--joined-out", type=Path)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--windows", nargs="+", type=int, default=list(DEFAULT_WINDOWS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    windows = tuple(sorted(set(int(w) for w in args.windows if int(w) > 0)))
    if not windows:
        raise SystemExit("Provide at least one positive window.")

    features = build_and_save_news_features(
        sources_jsonl=args.news_sources,
        signals_path=args.signals,
        out_path=args.features_out,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
        windows=windows,
    )
    print(f"Saved historical news features: {args.features_out}")
    print(f"Rows: {len(features):,}")
    display = [
        col
        for col in [
            "query",
            "date",
            "news_days_since_latest",
            "news_count_7d",
            "news_count_30d",
            "news_sentiment_weighted_30d",
            "news_sentiment_quality_weighted_30d",
            "media_news_count_30d",
            "market_news_count_30d",
            "official_filing_count_30d",
            "discovery_news_count_30d",
            "ml_allowed_news_count_30d",
            "official_source_count_30d",
            "official_confirmation_recent_30d",
            "requires_confirmation_count_30d",
            "unconfirmed_discovery_count_30d",
            "analyst_recommendation_count_90d",
            "analyst_pressure_latest_90d",
        ]
        if col in features.columns
    ]
    if display:
        print(features[display].sort_values(["date", "query"]).tail(25).to_string(index=False))

    if args.joined_out:
        joined = join_news_features_to_signals(
            signals_path=args.signals,
            news_features_path=args.features_out,
            out_path=args.joined_out,
            ticker_col=args.ticker_col,
            date_col=args.date_col,
        )
        print(f"Saved news-joined signals: {args.joined_out}")
        print(f"Joined rows: {len(joined):,}")


if __name__ == "__main__":
    main()
