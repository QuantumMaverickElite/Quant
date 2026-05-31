from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tabulate import tabulate

from backtester.engines.matrix_allocator_engine import (
    generate_run_samples,
    load_feature_matrix,
    load_price_matrix,
    prepare_market_matrices,
    run_batched_threshold_grid_for_sample,
    summarize_threshold_trials,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Threshold rebalance experiment using reusable matrix allocator engine."
    )

    parser.add_argument(
        "--feature-path",
        default="outputs/feature_matrix/rebalance_W/market_state_features.csv",
    )
    parser.add_argument(
        "--price-path",
        default="outputs/feature_matrix/rebalance_W/close_prices.csv",
    )

    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--sample-size", type=int, default=24)
    parser.add_argument("--portfolio-size", type=int, default=8)
    parser.add_argument("--capital", type=float, default=10_000.0)
    parser.add_argument("--max-weight", type=float, default=0.35)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.00, 0.01, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20],
    )

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact"],
        default="compact",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/threshold_rebalance/matrix_engine_weekly_sample24_port8",
    )

    parser.add_argument("--progress-every", type=int, default=100)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    features = load_feature_matrix(args.feature_path)
    prices = load_price_matrix(args.price_path)
    matrices = prepare_market_matrices(features, prices)

    thresholds = np.asarray(args.thresholds, dtype=float)

    run_samples = generate_run_samples(
        n_runs=args.runs,
        n_tickers=len(matrices.tickers),
        sample_size=args.sample_size,
        seed=args.seed,
    )

    out_dir = Path(args.output_dir)
    if args.save_mode != "none":
        out_dir.mkdir(parents=True, exist_ok=True)

    print("\nThreshold Rebalance Matrix Engine")
    print(f"Universe size: {len(matrices.tickers)}")
    print(f"Daily rows: {matrices.returns.shape[0]}")
    print(f"Check dates: {len(matrices.check_indices)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {min(args.sample_size, len(matrices.tickers))}")
    print(f"Portfolio size: {args.portfolio_size}")
    print(f"Thresholds: {args.thresholds}")
    print(f"Save mode: {args.save_mode}")

    rows = []

    for run_id, sample_indices in enumerate(run_samples, start=1):
        result = run_batched_threshold_grid_for_sample(
            matrices=matrices,
            sample_indices=sample_indices,
            thresholds=thresholds,
            portfolio_size=args.portfolio_size,
            max_weight=args.max_weight,
            capital=args.capital,
            run_id=run_id,
            save_curves=False,
        )

        result_rows = result.rows

        sampled_tickers = [matrices.tickers[i] for i in sample_indices]
        ticker_string = ",".join(sampled_tickers)

        for row in result_rows:
            rows.append(
                {
                    "run_id": run_id,
                    "tickers": ticker_string,
                    **row,
                }
            )

        if args.progress_every > 0 and run_id % args.progress_every == 0:
            print(f"completed runs={run_id}/{args.runs}")

    trials = pd.DataFrame(rows)
    summary = summarize_threshold_trials(trials)

    print("\nThreshold Comparison")
    print("=" * 120)
    print(
        tabulate(
            summary.round(4),
            headers="keys",
            tablefmt="github",
            showindex=False,
        )
    )
    print("=" * 120)

    if args.save_mode != "none":
        trials_path = out_dir / "threshold_trials.csv"
        summary_path = out_dir / "threshold_summary.csv"

        trials.to_csv(trials_path, index=False)
        summary.to_csv(summary_path, index=False)

        print(f"\nSaved: {trials_path}")
        print(f"Saved: {summary_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
