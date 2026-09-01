from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_adjustment import build_allocator_ready_signals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create allocator-ready signals with risk and opportunity scoring.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--confidence-col", default="adjusted_confidence")
    parser.add_argument(
        "--opportunity-features",
        type=Path,
        help="Optional CSV from score_event_opportunities/build_contextual_event_features to merge by ticker.",
    )
    parser.add_argument("--ticker-col", default="ticker")
    parser.add_argument("--include-historical", action="store_true")
    parser.add_argument("--disable-event-opportunity", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = build_allocator_ready_signals(
        signals_path=args.signals,
        out_path=args.out,
        confidence_col=args.confidence_col,
        latest_date_only=not args.include_historical,
        apply_event_opportunity=not args.disable_event_opportunity,
        opportunity_features_csv=args.opportunity_features,
        ticker_col=args.ticker_col,
    )
    print(f"Saved allocator-ready intelligence signals: {args.out}")
    print(f"Rows: {len(out):,}")
    if "intelligence_action_label" in out.columns:
        print(out["intelligence_action_label"].value_counts(dropna=False).to_string())
    if "event_opportunity_multiplier" in out.columns:
        evaluated = out[out.get("intelligence_action_label", "").ne("not_evaluated_historical_row")]
        cols = [
            col
            for col in [
                "ticker",
                "intelligence_action_label",
                "event_opportunity_score",
                "event_downside_risk_score",
                "event_opportunity_multiplier",
                "event_downside_multiplier",
                "net_event_multiplier",
                "allocator_confidence_pre_intelligence",
                "allocator_confidence_intelligence_adjusted",
            ]
            if col in evaluated.columns
        ]
        print(evaluated[cols].sort_values("allocator_confidence_intelligence_adjusted", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
