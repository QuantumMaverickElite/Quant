from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.calibration.walk_forward_calibrator import run_walk_forward_calibration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run walk-forward intelligence calibration without lookahead.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--target-col", default="success_10d")
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--predictions-out", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--heuristic-confidence-col")
    parser.add_argument("--model-type", choices=["logistic", "ridge"], default="logistic")
    parser.add_argument("--alpha", type=float, default=10.0)
    parser.add_argument("--train-days", type=int, default=252)
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--embargo-days", type=int, default=20)
    parser.add_argument("--min-train-rows", type=int, default=200)
    parser.add_argument("--min-test-rows", type=int, default=5)
    parser.add_argument("--rolling-train", action="store_true")
    parser.add_argument("--cash", type=float, default=10_000.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictions, summary = run_walk_forward_calibration(
        dataset_path=args.dataset,
        predictions_out=args.predictions_out,
        summary_out=args.summary_out,
        target_col=args.target_col,
        return_cols=tuple(args.return_cols),
        top_ns=tuple(args.top_ns),
        cash=args.cash,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
        baseline_confidence_col=args.baseline_confidence_col,
        heuristic_confidence_col=args.heuristic_confidence_col,
        model_type=args.model_type,
        alpha=args.alpha,
        train_days=args.train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        embargo_days=args.embargo_days,
        min_train_rows=args.min_train_rows,
        min_test_rows=args.min_test_rows,
        rolling_train=args.rolling_train,
    )
    print(f"Saved walk-forward predictions: {args.predictions_out}")
    print(f"Prediction rows: {len(predictions):,}")
    print(f"Saved walk-forward summary: {args.summary_out}")
    print(f"Summary rows: {len(summary):,}")
    if summary.empty:
        print(
            "No walk-forward folds were produced. "
            "Use a dataset with multiple historical signal dates or reduce train/min-row requirements for a smoke test."
        )
    else:
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
