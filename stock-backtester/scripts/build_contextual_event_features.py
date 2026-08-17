from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.events.event_feature_builder import build_event_features, load_events_jsonl, merge_event_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model-ready features from contextual market events.")
    parser.add_argument("--events", type=Path, default=Path("outputs/intelligence/contextual_events.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("outputs/intelligence/contextual_event_features.csv"))
    parser.add_argument("--merge-intelligence-features", type=Path)
    parser.add_argument("--merged-out", type=Path, default=Path("outputs/intelligence/intelligence_features_with_events.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = load_events_jsonl(args.events)
    features = build_event_features(events)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.out, index=False)
    print(f"Saved contextual event features: {args.out}")
    print(f"Rows: {len(features)}")
    if not features.empty:
        cols = [
            col
            for col in [
                "query",
                "contextual_event_risk",
                "mean_event_signed_impact",
                "macro_event_pressure",
                "sector_event_pressure",
                "ticker_event_pressure",
                "rates_event_pressure",
                "valuation_event_pressure",
                "event_count",
                "event_cluster_count",
            ]
            if col in features.columns
        ]
        print(features[cols].head(20).to_string(index=False))

    if args.merge_intelligence_features:
        merged = merge_event_features(
            intelligence_features_csv=args.merge_intelligence_features,
            event_features_csv=args.out,
            out_csv=args.merged_out,
        )
        print(f"Saved merged intelligence/event features: {args.merged_out}")
        print(f"Merged rows: {len(merged)}")


if __name__ == "__main__":
    main()
