from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate


DEFAULT_THRESHOLDS = [0.00, 0.01, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast NumPy threshold-rebalance Monte Carlo from feature matrix."
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

    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=DEFAULT_THRESHOLDS,
    )

    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact", "curves"],
        default="compact",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/threshold_rebalance/fast_v2_weekly_sample24_port8",
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print progress every N runs per threshold. Use 0 to disable.",
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
) -> dict[str, object]:
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

    score_matrix = score_df.iloc[valid_score_rows].to_numpy(dtype=float)
    check_indices_arr = np.asarray(check_indices, dtype=np.int64)

    return {
        "tickers": tickers,
        "price_dates": price_dates,
        "returns": returns.to_numpy(dtype=float),
        "score_matrix": score_matrix,
        "check_indices": check_indices_arr,
    }


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
    if equity.size == 0:
        return 0.0

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


def build_candidate_weights(
    scores: np.ndarray,
    sample_indices: np.ndarray,
    portfolio_size: int,
    max_weight: float,
    n_tickers: int,
) -> np.ndarray:
    sample_scores = scores[sample_indices]

    if sample_indices.size == 0:
        return np.zeros(n_tickers, dtype=float)

    n_hold = min(portfolio_size, sample_indices.size)
    top_local = np.argpartition(-sample_scores, kth=n_hold - 1)[:n_hold]

    top_indices = sample_indices[top_local]
    top_scores = scores[top_indices]

    order = np.argsort(-top_scores)
    top_indices = top_indices[order]

    weight = min(1.0 / n_hold, max_weight)

    weights = np.zeros(n_tickers, dtype=float)
    weights[top_indices] = weight

    return weights


def average_score_for_weights(scores: np.ndarray, weights: np.ndarray) -> float:
    holding_indices = np.flatnonzero(weights > 0)

    if holding_indices.size == 0:
        return 0.0

    return float(np.mean(scores[holding_indices]))


def turnover_pct(old_weights: np.ndarray, new_weights: np.ndarray) -> float:
    return float(np.sum(np.abs(new_weights - old_weights)) / 2.0 * 100.0)


def run_one_backtest(
    returns: np.ndarray,
    scores: np.ndarray,
    check_indices: np.ndarray,
    sample_indices: np.ndarray,
    threshold: float,
    portfolio_size: int,
    max_weight: float,
    capital: float,
) -> tuple[np.ndarray, dict[str, float]]:
    """
    Fast threshold backtest with position drift.

    Important:
    - Target weights are only applied on rebalance dates.
    - Between rebalances, position values drift with stock returns.
    - This avoids hidden daily rebalancing and better matches the original
      share-based backtest behavior.
    """
    n_days, n_tickers = returns.shape

    equity = np.empty(n_days, dtype=float)
    equity[0] = capital

    position_values = np.zeros(n_tickers, dtype=float)
    cash = capital
    target_weights = np.zeros(n_tickers, dtype=float)

    check_lookup = {
        int(day_idx): score_row_idx
        for score_row_idx, day_idx in enumerate(check_indices)
    }

    n_rebalances = 0
    turnovers = []

    def current_equity() -> float:
        return float(cash + np.sum(position_values))

    def current_weights() -> np.ndarray:
        total = current_equity()
        if total <= 0:
            return np.zeros(n_tickers, dtype=float)
        return position_values / total

    def apply_rebalance(new_weights: np.ndarray) -> None:
        nonlocal position_values, cash, target_weights

        total = current_equity()
        invested_weight = float(np.sum(new_weights))

        position_values = total * new_weights
        cash = max(total * (1.0 - invested_weight), 0.0)
        target_weights = new_weights.copy()

    if 0 in check_lookup:
        score_row = scores[check_lookup[0]]
        initial_weights = build_candidate_weights(
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

        if day in check_lookup:
            score_row = scores[check_lookup[day]]

            candidate_weights = build_candidate_weights(
                scores=score_row,
                sample_indices=sample_indices,
                portfolio_size=portfolio_size,
                max_weight=max_weight,
                n_tickers=n_tickers,
            )

            live_weights = current_weights()
            current_score = average_score_for_weights(score_row, live_weights)
            candidate_score = average_score_for_weights(score_row, candidate_weights)
            improvement = candidate_score - current_score

            has_positions = np.count_nonzero(position_values > 0) > 0

            if not has_positions or improvement >= threshold:
                turnovers.append(turnover_pct(live_weights, candidate_weights))
                apply_rebalance(candidate_weights)
                n_rebalances += 1
                equity[day] = current_equity()

    info = {
        "n_rebalances": float(n_rebalances),
        "mean_turnover_pct": float(np.mean(turnovers)) if turnovers else 0.0,
    }

    return equity, info


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


def main() -> None:
    args = parse_args()

    features = load_feature_matrix(args.feature_path)
    prices = load_price_matrix(args.price_path)

    matrices = prepare_matrices(features, prices)

    tickers = matrices["tickers"]
    price_dates = matrices["price_dates"]
    returns = matrices["returns"]
    scores = matrices["score_matrix"]
    check_indices = matrices["check_indices"]

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

    print("\nFast Threshold Rebalance v2")
    print(f"Universe size: {len(tickers)}")
    print(f"Daily rows: {returns.shape[0]}")
    print(f"Check dates: {len(check_indices)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {min(args.sample_size, len(tickers))}")
    print(f"Portfolio size: {args.portfolio_size}")
    print(f"Thresholds: {args.thresholds}")
    print(f"Save mode: {args.save_mode}")

    trial_rows = []
    equity_curve_rows = []

    for threshold in args.thresholds:
        print(f"\n=== Threshold {threshold:.4f} ===")

        for run_id, sample_indices in enumerate(run_samples, start=1):
            equity, info = run_one_backtest(
                returns=returns,
                scores=scores,
                check_indices=check_indices,
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

            trial_rows.append(
                {
                    "threshold": threshold,
                    "run_id": run_id,
                    "tickers": ",".join(sampled_tickers),
                    **metrics,
                    **info,
                }
            )

            if args.save_mode == "curves":
                curve = pd.DataFrame(
                    {
                        "date": price_dates,
                        "equity": equity,
                        "threshold": threshold,
                        "run_id": run_id,
                    }
                )
                equity_curve_rows.append(curve)

            if args.progress_every > 0 and run_id % args.progress_every == 0:
                print(
                    f"threshold={threshold:.4f} run={run_id:04d} "
                    f"return={metrics['total_return_pct']:.2f}% "
                    f"sharpe={metrics['sharpe']:.2f} "
                    f"rebalances={info['n_rebalances']:.0f}"
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
