from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.calibration.calibration_dataset import build_calibration_dataset, feature_columns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build intelligence calibration examples.")
    parser.add_argument("--labeled-signals", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--intelligence-features", type=Path)
    parser.add_argument("--event-features", type=Path)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = build_calibration_dataset(
        labeled_signals_path=args.labeled_signals,
        out_path=args.out,
        intelligence_features_csv=args.intelligence_features,
        event_features_csv=args.event_features,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
    )
    print(f"Saved calibration dataset: {args.out}")
    print(f"Rows: {len(out):,}")
    print(f"Feature columns: {len(feature_columns(out))}")


if __name__ == "__main__":
    main()
