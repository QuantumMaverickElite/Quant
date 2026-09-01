from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_feature_builder import (
    DEFAULT_WINDOWS,
    build_and_save_sec_features,
    join_sec_features_to_signals,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build point-in-time SEC filing features for intelligence training.")
    parser.add_argument("--sec-sources", required=True, type=Path, help="SEC source JSONL from fetch_sec_intelligence_sources.")
    parser.add_argument("--signals", required=True, type=Path, help="Signal table with ticker/query and date columns.")
    parser.add_argument(
        "--features-out",
        required=True,
        type=Path,
        help="Output SEC feature table, usually parquet or csv.",
    )
    parser.add_argument(
        "--joined-out",
        type=Path,
        help="Optional output signal table with SEC features joined on ticker/date.",
    )
    parser.add_argument("--ticker-col", default=None)
    parser.add_argument("--date-col", default=None)
    parser.add_argument("--windows", nargs="+", type=int, default=list(DEFAULT_WINDOWS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    windows = tuple(sorted(set(int(w) for w in args.windows if int(w) > 0)))
    if not windows:
        raise SystemExit("Provide at least one positive rolling window.")

    features = build_and_save_sec_features(
        sec_sources_jsonl=args.sec_sources,
        signals_path=args.signals,
        out_path=args.features_out,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
        windows=windows,
    )
    print(f"Saved SEC point-in-time features: {args.features_out}")
    print(f"Rows: {len(features):,}")
    print(f"Windows: {', '.join(str(w) + 'd' for w in windows)}")

    display = [
        col
        for col in [
            "query",
            "date",
            "sec_days_since_latest_filing",
            "sec_latest_form",
            "sec_filing_count_1d",
            "sec_filing_count_7d",
            "sec_filing_count_30d",
            "sec_filing_pressure_30d",
            "sec_has_8k_30d",
            "sec_has_10q_30d",
            "sec_has_10k_30d",
        ]
        if col in features.columns
    ]
    if display:
        print(features[display].sort_values(["date", "query"]).tail(25).to_string(index=False))

    if args.joined_out:
        joined = join_sec_features_to_signals(
            signals_path=args.signals,
            sec_features_path=args.features_out,
            out_path=args.joined_out,
            ticker_col=args.ticker_col,
            date_col=args.date_col,
        )
        print(f"Saved SEC-joined signals: {args.joined_out}")
        print(f"Joined rows: {len(joined):,}")


if __name__ == "__main__":
    main()
