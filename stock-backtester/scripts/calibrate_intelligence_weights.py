from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.weight_calibrator import calibrate_weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit first-pass bounded intelligence feature weights.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--target-col", default="signal_success")
    parser.add_argument("--out", default=Path("outputs/intelligence/calibration/intelligence_weight_calibration.json"), type=Path)
    parser.add_argument("--model-type", choices=["logistic", "ridge"], default="logistic")
    parser.add_argument("--alpha", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = calibrate_weights(
        dataset_path=args.dataset,
        target_col=args.target_col,
        out_json=args.out,
        model_type=args.model_type,
        alpha=args.alpha,
    )
    print(f"Saved calibration: {args.out}")
    print(f"Rows: {result['rows']}")
    print(f"Target mean: {result['target_mean']:.4f}")
    print("Top weights:")
    for feature, weight in list(result["weights"].items())[:20]:
        print(f"  {feature}: {weight:.6f}")


if __name__ == "__main__":
    main()
