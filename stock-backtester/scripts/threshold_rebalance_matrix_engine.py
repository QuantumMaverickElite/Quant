from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tabulate import tabulate

from backtester.engines.matrix_allocator_engine import (
    average_score_for_positions,
    average_score_for_weights,
    build_top_n_weights,
    generate_run_samples,
    load_feature_matrix,
    load_price_matrix,
    prepare_market_matrices,
    summarize_equity,
    turnover_pct,
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

    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
    )

    return parser.parse_args()


def run_one_threshold_backtest(
    returns: np.ndarray,
    scores: np.ndarray,
    check_indices: np.ndarray,
    price_dates: pd.DatetimeIndex,
    sample_indices: np.ndarray,
    threshold: float,
    portfolio_size: int,
    max_weight: float,
    capital: float,
) -> tuple[np.ndarray, dict[str, float]]:
    n_days, n_tickers = returns.shape

    equity = np.empty(n_days, dtype=float)
    equity[0] = capital

    position_values = np.zeros(n_tickers, dtype=float)
    cash = capital

    check_lookup = {
        int(day_idx): score_row_idx
        for score_row_idx, day_idx in enumerate(check_indices)
    }

    n_rebalances = 0
    turnovers: list[float] = []

    def current_equity() -> float:
        return float(cash + np.sum(position_values))

    def current_weights() -> np.ndarray:
        total = current_equity()
        if total <= 0:
            return np.zeros(n_tickers, dtype=float)
        return position_values / total

    def apply_rebalance(new_weights: np.ndarray) -> None:
        nonlocal position_values, cash

        total = current_equity()
        invested_weight = float(np.sum(new_weights))

        position_values = total * new_weights
        cash = max(total * (1.0 - invested_weight), 0.0)

    if 0 in check_lookup:
        score_row = scores[check_lookup[0]]
        initial_weights = build_top_n_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )
        turnovers.append(100.0)
        apply_rebalance(initial_weights)
        n_rebalances += 1
        equity[0] = current_equity()

    for day in range(1, n_days):
        position_values *= 1.0 + returns[day]
        equity[day] = current_equity()

        if day not in check_lookup:
            continue

        score_row = scores[check_lookup[day]]

        candidate_weights = build_top_n_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        current_score = average_score_for_positions(score_row, position_values)
        candidate_score = average_score_for_weights(score_row, candidate_weights)
        improvement = candidate_score - current_score

        has_positions = np.count_nonzero(position_values > 0) > 0

        if not has_positions or improvement >= threshold:
            live_weights = current_weights()
            turnovers.append(turnover_pct(live_weights, candidate_weights))
            apply_rebalance(candidate_weights)
            n_rebalances += 1
            equity[day] = current_equity()

    info = {
        "n_rebalances": float(n_rebalances),
        "mean_turnover_pct": float(np.mean(turnovers)) if turnovers else 0.0,
    }

    return equity, info


def summarize_trials(trials: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for threshold, group in trials.groupby("threshold"):
        rows.append(
            {
                "threshold": threshold,
                "mean_return_pct": group["total_return_pct"].mean(),
                "median_return_pct": group["total_return_pct"].median(),
                "mean_cagr_pct": group["cagr_pct"].mean(),
                "mean_sharpe": group["sharpe"].mean(),
                "median_sharpe": group["sharpe"].median(),
                "mean_max_drawdown_pct": group["max_drawdown_pct"].mean(),
                "prob_loss_pct": float((group["total_return_pct"] < 0).mean() * 100.0),
                "prob_sharpe_below_1_pct": float((group["sharpe"] < 1).mean() * 100.0),
                "mean_rebalances": group["n_rebalances"].mean(),
                "median_rebalances": group["n_rebalances"].median(),
                "mean_turnover_pct": group["mean_turnover_pct"].mean(),
            }
        )

    return pd.DataFrame(rows).sort_values("threshold")


def main() -> None:
    args = parse_args()

    features = load_feature_matrix(args.feature_path)
    prices = load_price_matrix(args.price_path)
    matrices = prepare_market_matrices(features, prices)

    tickers = matrices.tickers
    returns = matrices.returns
    scores = matrices.scores
    check_indices = matrices.check_indices
    price_dates = matrices.price_dates

    run_samples = generate_run_samples(
        n_runs=args.runs,
        n_tickers=len(tickers),
        sample_size=args.sample_size,
        seed=args.seed,
    )

    out_dir = Path(args.output_dir)
    if args.save_mode != "none":
        out_dir.mkdir(parents=True, exist_ok=True)

    print("\nThreshold Rebalance Matrix Engine")
    print(f"Universe size: {len(tickers)}")
    print(f"Daily rows: {returns.shape[0]}")
    print(f"Check dates: {len(check_indices)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {min(args.sample_size, len(tickers))}")
    print(f"Portfolio size: {args.portfolio_size}")
    print(f"Thresholds: {args.thresholds}")
    print(f"Save mode: {args.save_mode}")

    rows = []

    for threshold in args.thresholds:
        print(f"\n=== Threshold {threshold:.4f} ===")

        for run_id, sample_indices in enumerate(run_samples, start=1):
            equity, info = run_one_threshold_backtest(
                returns=returns,
                scores=scores,
                check_indices=check_indices,
                price_dates=price_dates,
                sample_indices=sample_indices,
                threshold=threshold,
                portfolio_size=args.portfolio_size,
                max_weight=args.max_weight,
                capital=args.capital,
            )

            metrics = summarize_equity(
                equity=equity,
                dates=price_dates,
                capital=args.capital,
            )

            sampled_tickers = [tickers[i] for i in sample_indices]

            rows.append(
                {
                    "threshold": threshold,
                    "run_id": run_id,
                    "tickers": ",".join(sampled_tickers),
                    **metrics,
                    **info,
                }
            )

            if args.progress_every > 0 and run_id % args.progress_every == 0:
                print(
                    f"threshold={threshold:.4f} run={run_id:04d} "
                    f"return={metrics['total_return_pct']:.2f}% "
                    f"sharpe={metrics['sharpe']:.2f} "
                    f"rebalances={info['n_rebalances']:.0f}"
                )

    trials = pd.DataFrame(rows)
    summary = summarize_trials(trials)

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
