from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.calibrated_adjustment import apply_calibrated_intelligence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply calibrated intelligence weights to allocator signals.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--baseline-confidence-col", default="allocator_confidence_pre_intelligence")
    parser.add_argument("--heuristic-confidence-col", default="allocator_confidence_intelligence_adjusted")
    parser.add_argument("--min-multiplier", type=float, default=0.70)
    parser.add_argument("--max-multiplier", type=float, default=1.15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = apply_calibrated_intelligence(
        signals_path=args.signals,
        calibration_json=args.calibration,
        out_path=args.out,
        baseline_confidence_col=args.baseline_confidence_col,
        heuristic_confidence_col=args.heuristic_confidence_col,
        min_multiplier=args.min_multiplier,
        max_multiplier=args.max_multiplier,
    )
    print(f"Saved ML-calibrated intelligence signals: {args.out}")
    print(f"Rows: {len(out):,}")
    display = [
        col
        for col in [
            "ticker",
            "allocator_confidence_pre_intelligence",
            "allocator_confidence_intelligence_adjusted",
            "allocator_confidence_ml_intelligence_adjusted",
            "ml_intelligence_multiplier",
            "ml_intelligence_probability",
            "regime_break_score",
            "price_action_risk",
            "sentiment_score",
            "event_opportunity_score",
            "event_downside_risk_score",
        ]
        if col in out.columns
    ]
    if display:
        print(out[display].sort_values("allocator_confidence_ml_intelligence_adjusted", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
