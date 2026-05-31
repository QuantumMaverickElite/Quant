from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate


DEFAULT_THRESHOLDS = [0.00, 0.01, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20]

_RETURNS: np.ndarray | None = None
_SCORES: np.ndarray | None = None
_CHECK_INDICES: np.ndarray | None = None
_PRICE_DATES: pd.DatetimeIndex | None = None
_TICKERS: list[str] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast v3 threshold-rebalance Monte Carlo with batched thresholds and multiprocessing."
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
        default=DEFAULT_THRESHOLDS,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=max((os.cpu_count() or 2) - 1, 1),
        help="Number of worker processes. Use 1 to disable multiprocessing.",
    )

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact", "curves"],
        default="compact",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/threshold_rebalance/fast_v3_weekly_sample24_port8",
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print progress every N completed runs. Use 0 to disable.",
    )

    return parser.parse_args()


def load_feature_matrix(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str)

    if "adjusted_score" not in df.columns:
        raise ValueError("Feature matrix must contain adjusted_score.")

    df["adjusted_score"] = pd.to_numeric(
        df["adjusted_score"],
        errors="coerce",
    ).fillna(0.0)

    return df.sort_values(["date", "ticker"]).reset_index(drop=True)


def load_price_matrix(path: str | Path) -> pd.DataFrame:
    prices = pd.read_csv(path)

    first_col = prices.columns[0]
    prices[first_col] = pd.to_datetime(prices[first_col])
    prices = prices.rename(columns={first_col: "date"})
    prices = prices.set_index("date").sort_index()

    for col in prices.columns:
        prices[col] = pd.to_numeric(prices[col], errors="coerce")

    return prices


def prepare_matrices(
    features: pd.DataFrame,
    prices: pd.DataFrame,
) -> dict[str, Any]:
    tickers = sorted(set(features["ticker"]).intersection(prices.columns))

    if not tickers:
        raise ValueError("No overlapping tickers between features and prices.")

    features = features[features["ticker"].isin(tickers)].copy()
    prices = prices[tickers].copy()

    score_df = (
        features.pivot_table(
            index="date",
            columns="ticker",
            values="adjusted_score",
            aggfunc="last",
        )
        .reindex(columns=tickers)
        .sort_index()
        .fillna(0.0)
    )

    start = score_df.index.min()
    end = score_df.index.max()

    prices = prices[(prices.index >= start) & (prices.index <= end)].copy()
    prices = prices.ffill().bfill()

    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)

    score_dates = score_df.index
    price_dates = prices.index

    check_indices = []
    valid_score_rows = []

    for i, date in enumerate(score_dates):
        pos = price_dates.searchsorted(date)

        if pos < len(price_dates) and price_dates[pos] == date:
            check_indices.append(pos)
            valid_score_rows.append(i)
        elif pos > 0:
            check_indices.append(pos - 1)
            valid_score_rows.append(i)

    if not check_indices:
        raise ValueError("No check dates align with price dates.")

    return {
        "tickers": tickers,
        "price_dates": price_dates,
        "returns": returns.to_numpy(dtype=float),
        "scores": score_df.iloc[valid_score_rows].to_numpy(dtype=float),
        "check_indices": np.asarray(check_indices, dtype=np.int64),
    }


def init_worker(
    returns: np.ndarray,
    scores: np.ndarray,
    check_indices: np.ndarray,
    price_dates: pd.DatetimeIndex,
    tickers: list[str],
) -> None:
    global _RETURNS, _SCORES, _CHECK_INDICES, _PRICE_DATES, _TICKERS

    _RETURNS = returns
    _SCORES = scores
    _CHECK_INDICES = check_indices
    _PRICE_DATES = price_dates
    _TICKERS = tickers


def max_drawdown(equity: np.ndarray) -> float:
    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    return float(np.min(drawdown) * 100.0)


def sharpe_ratio(equity: np.ndarray) -> float:
    if equity.size < 2:
        return 0.0

    returns = equity[1:] / equity[:-1] - 1.0
    std = np.std(returns)

    if std == 0 or not np.isfinite(std):
        return 0.0

    return float((np.mean(returns) / std) * np.sqrt(252))


def cagr(equity: np.ndarray, dates: pd.DatetimeIndex) -> float:
    start = float(equity[0])
    end = float(equity[-1])

    if start <= 0:
        return 0.0

    days = max((dates[-1] - dates[0]).days, 1)
    years = days / 365.25

    return float(((end / start) ** (1.0 / years) - 1.0) * 100.0)


def summarize_equity(
    equity: np.ndarray,
    dates: pd.DatetimeIndex,
    capital: float,
) -> dict[str, float]:
    final_equity = float(equity[-1])
    total_return_pct = (final_equity / capital - 1.0) * 100.0

    return {
        "final_equity": final_equity,
        "total_return_pct": float(total_return_pct),
        "cagr_pct": cagr(equity, dates),
        "max_drawdown_pct": max_drawdown(equity),
        "sharpe": sharpe_ratio(equity),
    }


def build_candidate_weights(
    scores: np.ndarray,
    sample_indices: np.ndarray,
    portfolio_size: int,
    max_weight: float,
    n_tickers: int,
) -> np.ndarray:
    """
    Deterministic top-N equal-weight candidate allocator.

    Avoid np.argpartition here. It is fast, but it is not stable when scores
    tie. Different NumPy versions can choose different names among tied scores,
    which changes frequent-rebalance paths.

    Tie break:
    1. Higher score first.
    2. Lower ticker index first.
    """
    weights = np.zeros(n_tickers, dtype=float)

    if sample_indices.size == 0:
        return weights

    sample_indices = np.asarray(sample_indices, dtype=int)
    sample_scores = np.asarray(scores[sample_indices], dtype=float)

    n_hold = min(portfolio_size, int(sample_indices.size))
    if n_hold <= 0:
        return weights

    order = np.lexsort((sample_indices, -sample_scores))
    top_indices = sample_indices[order[:n_hold]]

    weight = min(1.0 / n_hold, max_weight)
    weights[top_indices] = weight

    return weights


def average_score_for_position_values(scores: np.ndarray, position_values: np.ndarray) -> float:
    holding_indices = np.flatnonzero(position_values > 0)

    if holding_indices.size == 0:
        return 0.0

    return float(np.mean(scores[holding_indices]))


def average_score_for_weights(scores: np.ndarray, weights: np.ndarray) -> float:
    holding_indices = np.flatnonzero(weights > 0)

    if holding_indices.size == 0:
        return 0.0

    return float(np.mean(scores[holding_indices]))


def turnover_pct(old_weights: np.ndarray, new_weights: np.ndarray) -> float:
    return float(np.sum(np.abs(new_weights - old_weights)) / 2.0 * 100.0)


def run_one_sample_all_thresholds(
    run_id: int,
    sample_indices: np.ndarray,
    thresholds: np.ndarray,
    portfolio_size: int,
    max_weight: float,
    capital: float,
    save_curves: bool,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame]]:
    if _RETURNS is None or _SCORES is None or _CHECK_INDICES is None or _PRICE_DATES is None or _TICKERS is None:
        raise RuntimeError("Worker globals are not initialized.")

    returns = _RETURNS
    scores = _SCORES
    check_indices = _CHECK_INDICES
    price_dates = _PRICE_DATES
    tickers = _TICKERS

    n_days, n_tickers = returns.shape
    n_thresholds = thresholds.size

    equity = np.empty((n_thresholds, n_days), dtype=float)
    equity[:, 0] = capital

    position_values = np.zeros((n_thresholds, n_tickers), dtype=float)
    cash = np.full(n_thresholds, capital, dtype=float)

    n_rebalances = np.zeros(n_thresholds, dtype=float)
    turnover_sums = np.zeros(n_thresholds, dtype=float)
    turnover_counts = np.zeros(n_thresholds, dtype=float)

    check_lookup = {
        int(day_idx): score_row_idx
        for score_row_idx, day_idx in enumerate(check_indices)
    }

    def current_equity_vec() -> np.ndarray:
        return cash + position_values.sum(axis=1)

    def current_weights_matrix() -> np.ndarray:
        totals = current_equity_vec()
        out = np.zeros_like(position_values)
        valid = totals > 0
        out[valid] = position_values[valid] / totals[valid, None]
        return out

    def apply_rebalance(mask: np.ndarray, new_weights: np.ndarray) -> None:
        nonlocal position_values, cash

        if not np.any(mask):
            return

        totals = current_equity_vec()
        invested_weight = float(np.sum(new_weights))

        position_values[mask] = totals[mask, None] * new_weights[None, :]
        cash[mask] = np.maximum(totals[mask] * (1.0 - invested_weight), 0.0)

    if 0 in check_lookup:
        score_row = scores[check_lookup[0]]
        initial_weights = build_candidate_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        all_mask = np.ones(n_thresholds, dtype=bool)
        apply_rebalance(all_mask, initial_weights)

        n_rebalances += 1.0
        turnover_sums += 100.0
        turnover_counts += 1.0
        equity[:, 0] = current_equity_vec()

    for day in range(1, n_days):
        position_values *= 1.0 + returns[day][None, :]
        equity[:, day] = current_equity_vec()

        if day not in check_lookup:
            continue

        score_row = scores[check_lookup[day]]
        candidate_weights = build_candidate_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        candidate_score = average_score_for_weights(score_row, candidate_weights)

        current_scores = np.array(
            [
                average_score_for_position_values(score_row, position_values[i])
                for i in range(n_thresholds)
            ],
            dtype=float,
        )

        improvements = candidate_score - current_scores
        has_positions = (position_values > 0).any(axis=1)

        rebalance_mask = (~has_positions) | (improvements >= thresholds)

        if np.any(rebalance_mask):
            live_weights = current_weights_matrix()
            turnovers = np.array(
                [
                    turnover_pct(live_weights[i], candidate_weights)
                    for i in range(n_thresholds)
                ],
                dtype=float,
            )

            turnover_sums[rebalance_mask] += turnovers[rebalance_mask]
            turnover_counts[rebalance_mask] += 1.0
            n_rebalances[rebalance_mask] += 1.0

            apply_rebalance(rebalance_mask, candidate_weights)
            equity[:, day] = current_equity_vec()

    sampled_tickers = [tickers[i] for i in sample_indices]
    ticker_string = ",".join(sampled_tickers)

    trial_rows: list[dict[str, Any]] = []
    curve_rows: list[pd.DataFrame] = []

    for threshold_idx, threshold in enumerate(thresholds):
        eq = equity[threshold_idx]
        metrics = summarize_equity(eq, price_dates, capital)

        mean_turnover = (
            turnover_sums[threshold_idx] / turnover_counts[threshold_idx]
            if turnover_counts[threshold_idx] > 0
            else 0.0
        )

        trial_rows.append(
            {
                "threshold": float(threshold),
                "run_id": run_id,
                "tickers": ticker_string,
                **metrics,
                "n_rebalances": float(n_rebalances[threshold_idx]),
                "mean_turnover_pct": float(mean_turnover),
            }
        )

        if save_curves:
            curve_rows.append(
                pd.DataFrame(
                    {
                        "date": price_dates,
                        "equity": eq,
                        "threshold": float(threshold),
                        "run_id": run_id,
                    }
                )
            )

    return trial_rows, curve_rows


def generate_run_samples(
    rng: np.random.Generator,
    n_runs: int,
    n_tickers: int,
    sample_size: int,
) -> list[np.ndarray]:
    size = min(sample_size, n_tickers)

    return [
        np.sort(rng.choice(n_tickers, size=size, replace=False)).astype(np.int64)
        for _ in range(n_runs)
    ]


def summarize_distribution(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    rows = []

    for metric in metrics:
        values = pd.to_numeric(df[metric], errors="coerce").dropna()

        if values.empty:
            continue

        rows.append(
            {
                "metric": metric,
                "mean": values.mean(),
                "median": values.median(),
                "std": values.std(ddof=0),
                "min": values.min(),
                "p05": values.quantile(0.05),
                "p25": values.quantile(0.25),
                "p75": values.quantile(0.75),
                "p95": values.quantile(0.95),
                "max": values.max(),
            }
        )

    return pd.DataFrame(rows)


def build_summary(trials: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []

    for threshold, group in trials.groupby("threshold"):
        dist = summarize_distribution(
            group,
            metrics=[
                "total_return_pct",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
                "final_equity",
                "n_rebalances",
                "mean_turnover_pct",
            ],
        )

        metric_map = {row["metric"]: row for _, row in dist.iterrows()}

        summary_rows.append(
            {
                "threshold": threshold,
                "mean_return_pct": metric_map["total_return_pct"]["mean"],
                "median_return_pct": metric_map["total_return_pct"]["median"],
                "mean_cagr_pct": metric_map["cagr_pct"]["mean"],
                "mean_sharpe": metric_map["sharpe"]["mean"],
                "median_sharpe": metric_map["sharpe"]["median"],
                "mean_max_drawdown_pct": metric_map["max_drawdown_pct"]["mean"],
                "prob_loss_pct": float((group["total_return_pct"] < 0).mean() * 100.0),
                "prob_sharpe_below_1_pct": float((group["sharpe"] < 1).mean() * 100.0),
                "mean_rebalances": metric_map["n_rebalances"]["mean"],
                "median_rebalances": metric_map["n_rebalances"]["median"],
                "mean_turnover_pct": metric_map["mean_turnover_pct"]["mean"],
            }
        )

    return pd.DataFrame(summary_rows).sort_values("threshold")


def plot_threshold_bars(summary: pd.DataFrame, out_dir: Path) -> None:
    charts = [
        ("mean_return_pct", "Mean Total Return (%)", "threshold_mean_return_pct.png"),
        ("median_return_pct", "Median Total Return (%)", "threshold_median_return_pct.png"),
        ("mean_sharpe", "Mean Sharpe", "threshold_mean_sharpe.png"),
        ("prob_loss_pct", "Probability of Loss (%)", "threshold_prob_loss_pct.png"),
        ("mean_rebalances", "Mean Number of Rebalances", "threshold_mean_rebalances.png"),
        ("mean_turnover_pct", "Mean Turnover Per Rebalance (%)", "threshold_mean_turnover_pct.png"),
    ]

    for column, title, filename in charts:
        if column not in summary.columns:
            continue

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(summary["threshold"].astype(str), summary[column])
        ax.set_title(title)
        ax.set_xlabel("Threshold")
        ax.set_ylabel(title)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()

        fig.savefig(out_dir / filename, dpi=150, bbox_inches="tight")
        plt.close(fig)


def plot_median_curves(equity_curves: pd.DataFrame, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))

    for threshold, group in equity_curves.groupby("threshold"):
        matrix = group.pivot_table(
            index="date",
            columns="run_id",
            values="equity",
            aggfunc="last",
        ).sort_index()

        median_curve = matrix.median(axis=1)

        ax.plot(
            median_curve.index,
            median_curve.values,
            linewidth=2.2,
            label=str(threshold),
        )

    ax.axhline(10_000, linestyle=":", linewidth=1.5, label="Starting capital")
    ax.set_title("Median Strategy Equity Curve by Threshold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Threshold")
    fig.tight_layout()

    fig.savefig(out_dir / "threshold_median_equity_curves.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_threshold_spaghetti(equity_curves: pd.DataFrame, out_dir: Path) -> None:
    spaghetti_dir = out_dir / "spaghetti"
    spaghetti_dir.mkdir(parents=True, exist_ok=True)

    for threshold, group in equity_curves.groupby("threshold"):
        matrix = group.pivot_table(
            index="date",
            columns="run_id",
            values="equity",
            aggfunc="last",
        ).sort_index()

        median_curve = matrix.median(axis=1)
        p25_curve = matrix.quantile(0.25, axis=1)
        p75_curve = matrix.quantile(0.75, axis=1)

        fig, ax = plt.subplots(figsize=(12, 7))

        for run_id in matrix.columns:
            ax.plot(matrix.index, matrix[run_id], alpha=0.12, linewidth=0.8)

        ax.plot(median_curve.index, median_curve.values, linewidth=2.5, label="Median path")
        ax.plot(p25_curve.index, p25_curve.values, linestyle="--", linewidth=2.0, label="25th percentile path")
        ax.plot(p75_curve.index, p75_curve.values, linestyle="--", linewidth=2.0, label="75th percentile path")
        ax.axhline(10_000, linestyle=":", linewidth=1.5, label="Starting capital")

        ax.set_title(f"Threshold Rebalance Spaghetti: threshold={threshold}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Equity")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        label = str(threshold).replace(".", "p")
        fig.savefig(spaghetti_dir / f"threshold_{label}_spaghetti.png", dpi=150, bbox_inches="tight")
        plt.close(fig)


def run_one_sample_task(
    task: tuple[int, np.ndarray, np.ndarray, int, float, float, bool],
) -> tuple[list[dict[str, Any]], list[pd.DataFrame]]:
    return run_one_sample_all_thresholds(*task)


def run_tasks(
    tasks: list[tuple[int, np.ndarray, np.ndarray, int, float, float, bool]],
    workers: int,
    returns: np.ndarray,
    scores: np.ndarray,
    check_indices: np.ndarray,
    price_dates: pd.DatetimeIndex,
    tickers: list[str],
    progress_every: int,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame]]:
    trial_rows: list[dict[str, Any]] = []
    curve_rows: list[pd.DataFrame] = []

    if workers <= 1:
        init_worker(returns, scores, check_indices, price_dates, tickers)

        for completed, task in enumerate(tasks, start=1):
            rows, curves = run_one_sample_all_thresholds(*task)
            trial_rows.extend(rows)
            curve_rows.extend(curves)

            if progress_every > 0 and completed % progress_every == 0:
                print(f"completed runs={completed}/{len(tasks)}")

        return trial_rows, curve_rows

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=init_worker,
        initargs=(returns, scores, check_indices, price_dates, tickers),
    ) as executor:
        for completed, result in enumerate(executor.map(run_one_sample_task, tasks), start=1):
            rows, curves = result
            trial_rows.extend(rows)
            curve_rows.extend(curves)

            if progress_every > 0 and completed % progress_every == 0:
                print(f"completed runs={completed}/{len(tasks)}")

    return trial_rows, curve_rows


def main() -> None:
    args = parse_args()

    features = load_feature_matrix(args.feature_path)
    prices = load_price_matrix(args.price_path)

    matrices = prepare_matrices(features, prices)

    tickers = matrices["tickers"]
    price_dates = matrices["price_dates"]
    returns = matrices["returns"]
    scores = matrices["scores"]
    check_indices = matrices["check_indices"]

    thresholds = np.asarray(args.thresholds, dtype=float)

    rng = np.random.default_rng(args.seed)
    run_samples = generate_run_samples(
        rng=rng,
        n_runs=args.runs,
        n_tickers=len(tickers),
        sample_size=args.sample_size,
    )

    out_dir = Path(args.output_dir)

    if args.save_mode != "none":
        out_dir.mkdir(parents=True, exist_ok=True)

    print("\nFast Threshold Rebalance v3")
    print(f"Universe size: {len(tickers)}")
    print(f"Daily rows: {returns.shape[0]}")
    print(f"Check dates: {len(check_indices)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {min(args.sample_size, len(tickers))}")
    print(f"Portfolio size: {args.portfolio_size}")
    print(f"Thresholds: {args.thresholds}")
    print(f"Workers: {args.workers}")
    print(f"Save mode: {args.save_mode}")

    tasks = [
        (
            run_id,
            sample_indices,
            thresholds,
            args.portfolio_size,
            args.max_weight,
            args.capital,
            args.save_mode == "curves",
        )
        for run_id, sample_indices in enumerate(run_samples, start=1)
    ]

    trial_rows, equity_curve_rows = run_tasks(
        tasks=tasks,
        workers=args.workers,
        returns=returns,
        scores=scores,
        check_indices=check_indices,
        price_dates=price_dates,
        tickers=tickers,
        progress_every=args.progress_every,
    )

    trials = pd.DataFrame(trial_rows)
    summary = build_summary(trials)

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

        plot_threshold_bars(summary, out_dir)

        if args.save_mode == "curves" and equity_curve_rows:
            curves = pd.concat(equity_curve_rows, ignore_index=True)
            curves_path = out_dir / "threshold_equity_curves.csv"

            curves.to_csv(curves_path, index=False)
            plot_median_curves(curves, out_dir)
            plot_threshold_spaghetti(curves, out_dir)

            print(f"Saved: {curves_path}")
            print(f"Saved: {out_dir / 'threshold_median_equity_curves.png'}")
            print(f"Saved spaghetti plots: {out_dir / 'spaghetti'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
