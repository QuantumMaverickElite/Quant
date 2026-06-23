from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.signal_integration import integrate_intelligence_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Join latest intelligence features into a signal table.")
    parser.add_argument("--signals", required=True, type=Path, help="Input CSV/parquet signal table.")
    parser.add_argument("--features", default=Path("outputs/intelligence/intelligence_features.csv"), type=Path)
    parser.add_argument("--out", required=True, type=Path, help="Output CSV/parquet signal table.")
    parser.add_argument("--ticker-col", help="Ticker column override.")
    parser.add_argument("--date-col", help="Date column override.")
    parser.add_argument("--latest-date-only", action="store_true", help="Apply current intelligence only to the newest signal date.")
    parser.add_argument("--confidence-col", help="Confidence/score column override.")
    parser.add_argument("--penalty-strength", type=float, default=0.75)
    parser.add_argument("--min-multiplier", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = integrate_intelligence_features(
        signals_path=args.signals,
        features_csv=args.features,
        out_path=args.out,
        ticker_col=args.ticker_col,
        confidence_col=args.confidence_col,
        penalty_strength=args.penalty_strength,
        min_multiplier=args.min_multiplier,
        date_col=args.date_col,
        latest_date_only=args.latest_date_only,
    )
    print(f"Saved intelligence-adjusted signals: {args.out}")
    print(f"Rows: {len(out)}")
    if "intelligence_action_label" in out.columns:
        print(out["intelligence_action_label"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
