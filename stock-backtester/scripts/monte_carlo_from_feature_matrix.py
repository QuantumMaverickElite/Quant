from __future__ import annotations

import argparse
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast Monte Carlo using prebuilt MarketState feature matrix."
    )

    parser.add_argument(
        "--feature-path",
        default="outputs/feature_matrix/market_state_v1/market_state_features.csv",
        help="Path to market_state_features.csv.",
    )

    parser.add_argument(
        "--price-path",
        default="outputs/feature_matrix/market_state_v1/close_prices.csv",
        help="Path to close_prices.csv.",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=100,
        help="Number of Monte Carlo runs. Default: 100",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=12,
        help="Number of tickers per run. Default: 12",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed. Default: 42",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=10_000.0,
        help="Starting capital. Default: 10000",
    )

    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.35,
        help="Global maximum weight per ticker. Default: 0.35",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/monte_carlo/feature_matrix_v1",
        help="Output directory.",
    )

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact", "curves", "full"],
        default="compact",
        help=(
            "Output mode. none=print only, compact=summary CSVs only, "
            "curves=compact+combined equity curves+plots, "
            "full=curves+per-run folders. Default: compact"
        ),
    )

    return parser.parse_args()


def assign_weights(
    rebalance_df: pd.DataFrame,
    max_weight: float,
) -> pd.DataFrame:
    out = rebalance_df.copy()

    out["target_weight"] = 0.0

    allowed = (out["allow_new_equity_positions"] == True) & (out["adjusted_score"] > 0)

    allowed_df = out.loc[allowed].copy()

    if allowed_df.empty:
        return out

    score_sum = allowed_df["adjusted_score"].sum()

    if score_sum <= 0:
        return out

    target_gross_exposure = float(
        np.clip(allowed_df["combined_multiplier"].mean(), 0.0, 1.0)
    )

    raw_weights = (allowed_df["adjusted_score"] / score_sum) * target_gross_exposure

    capped_weights = raw_weights.clip(upper=max_weight)

    out.loc[allowed_df.index, "target_weight"] = capped_weights

    return out


def compute_portfolio_equity(
    close_prices: pd.DataFrame,
    weights_by_date: dict[pd.Timestamp, dict[str, float]],
    capital: float,
) -> pd.DataFrame:
    close = close_prices.copy().sort_index().ffill()
    returns = close.pct_change().fillna(0.0)

    rebalance_dates = sorted(weights_by_date.keys())

    if not rebalance_dates:
        raise ValueError("No rebalance dates available.")

    start = rebalance_dates[0]
    end = returns.index.max()

    returns = returns[(returns.index >= start) & (returns.index <= end)]

    if returns.empty:
        raise ValueError("No returns available for selected simulation window.")

    weights = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    weights[:] = np.nan

    for date, weight_map in weights_by_date.items():
        if date in weights.index:
            for ticker, weight in weight_map.items():
                if ticker in weights.columns:
                    weights.loc[date, ticker] = weight

    weights = weights.ffill().fillna(0.0)

    portfolio_returns = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    equity = capital * (1.0 + portfolio_returns).cumprod()

    return pd.DataFrame(
        {
            "portfolio_return": portfolio_returns,
            "equity": equity,
        },
        index=returns.index,
    )


def compute_equal_weight_rebalance_equity(
    close_prices: pd.DataFrame,
    tickers: list[str],
    rebalance_dates: list[pd.Timestamp],
    capital: float,
) -> pd.DataFrame:
    available_tickers = [ticker for ticker in tickers if ticker in close_prices.columns]

    if not available_tickers:
        raise ValueError("No sampled tickers found in close price matrix.")

    weight = 1.0 / len(available_tickers)

    weights_by_date = {
        pd.Timestamp(date): {ticker: weight for ticker in available_tickers}
        for date in rebalance_dates
    }

    return compute_portfolio_equity(
        close_prices=close_prices[available_tickers],
        weights_by_date=weights_by_date,
        capital=capital,
    )


def compute_equal_weight_buy_hold_equity(
    close_prices: pd.DataFrame,
    tickers: list[str],
    start_date: pd.Timestamp,
    capital: float,
) -> pd.DataFrame:
    available_tickers = [ticker for ticker in tickers if ticker in close_prices.columns]

    if not available_tickers:
        raise ValueError("No sampled tickers found in close price matrix.")

    close = close_prices[available_tickers].copy().sort_index().ffill()
    close = close[close.index >= start_date]

    if close.empty:
        raise ValueError("No prices available for buy-and-hold benchmark.")

    first_prices = close.iloc[0].replace(0, np.nan)
    normalized = close / first_prices

    equity = capital * normalized.mean(axis=1)
    portfolio_return = equity.pct_change().fillna(0.0)

    return pd.DataFrame(
        {
            "portfolio_return": portfolio_return,
            "equity": equity,
        },
        index=close.index,
    )


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def summarize_equity(equity_curve: pd.DataFrame, capital: float) -> dict:
    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return = final_equity / capital - 1.0

    days = len(equity_curve)
    years = days / 252.0

    if years > 0:
        cagr = (final_equity / capital) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0

    daily_returns = equity_curve["portfolio_return"]

    if daily_returns.std(ddof=0) > 0:
        sharpe = (daily_returns.mean() / daily_returns.std(ddof=0)) * np.sqrt(252)
    else:
        sharpe = 0.0

    return {
        "start_equity": capital,
        "final_equity": final_equity,
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": max_drawdown(equity_curve["equity"]) * 100,
        "sharpe": sharpe,
    }


def prefix_summary(summary: dict, prefix: str) -> dict:
    return {f"{prefix}_{key}": value for key, value in summary.items()}


def run_one_simulation(
    run_id: int,
    tickers: list[str],
    features: pd.DataFrame,
    close_prices: pd.DataFrame,
    capital: float,
    max_weight: float,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    subset_features = features[features["ticker"].isin(tickers)].copy()

    if subset_features.empty:
        raise ValueError("No feature rows for sampled tickers.")

    rebalance_dates = sorted(pd.to_datetime(subset_features["date"]).unique())

    weights_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    rebalance_logs = []

    for date in rebalance_dates:
        date = pd.Timestamp(date)

        rebalance_df = subset_features[
            pd.to_datetime(subset_features["date"]) == date
        ].copy()

        rebalance_df = assign_weights(
            rebalance_df=rebalance_df,
            max_weight=max_weight,
        )

        weight_map = {
            row["ticker"]: float(row["target_weight"])
            for _, row in rebalance_df.iterrows()
        }

        weights_by_date[date] = weight_map
        rebalance_df["run_id"] = run_id
        rebalance_logs.append(rebalance_df)

    sim_price_cols = [ticker for ticker in tickers if ticker in close_prices.columns]

    if not sim_price_cols:
        raise ValueError("No sampled tickers found in close price matrix.")

    sim_prices = close_prices[sim_price_cols].copy()

    strategy_equity = compute_portfolio_equity(
        close_prices=sim_prices,
        weights_by_date=weights_by_date,
        capital=capital,
    )

    equal_weight_rebalance_equity = compute_equal_weight_rebalance_equity(
        close_prices=sim_prices,
        tickers=tickers,
        rebalance_dates=rebalance_dates,
        capital=capital,
    )

    equal_weight_buy_hold_equity = compute_equal_weight_buy_hold_equity(
        close_prices=sim_prices,
        tickers=tickers,
        start_date=pd.Timestamp(rebalance_dates[0]),
        capital=capital,
    )

    strategy_summary = summarize_equity(strategy_equity, capital=capital)
    equal_weight_rebalance_summary = summarize_equity(
        equal_weight_rebalance_equity,
        capital=capital,
    )
    equal_weight_buy_hold_summary = summarize_equity(
        equal_weight_buy_hold_equity,
        capital=capital,
    )

    summary = {
        **strategy_summary,
        **prefix_summary(equal_weight_rebalance_summary, "ew_rebalance"),
        **prefix_summary(equal_weight_buy_hold_summary, "ew_buy_hold"),
    }

    summary["excess_return_vs_ew_rebalance_pct"] = (
        summary["total_return_pct"] - summary["ew_rebalance_total_return_pct"]
    )
    summary["excess_return_vs_ew_buy_hold_pct"] = (
        summary["total_return_pct"] - summary["ew_buy_hold_total_return_pct"]
    )

    summary["drawdown_improvement_vs_ew_rebalance_pct"] = (
        summary["max_drawdown_pct"] - summary["ew_rebalance_max_drawdown_pct"]
    )
    summary["drawdown_improvement_vs_ew_buy_hold_pct"] = (
        summary["max_drawdown_pct"] - summary["ew_buy_hold_max_drawdown_pct"]
    )

    summary["sharpe_diff_vs_ew_rebalance"] = (
        summary["sharpe"] - summary["ew_rebalance_sharpe"]
    )
    summary["sharpe_diff_vs_ew_buy_hold"] = (
        summary["sharpe"] - summary["ew_buy_hold_sharpe"]
    )

    summary["beat_ew_rebalance_return"] = (
        summary["total_return_pct"] > summary["ew_rebalance_total_return_pct"]
    )
    summary["beat_ew_buy_hold_return"] = (
        summary["total_return_pct"] > summary["ew_buy_hold_total_return_pct"]
    )

    ticker_string = " ".join(tickers)

    summary["run_id"] = run_id
    summary["tickers"] = ticker_string
    summary["num_tickers"] = len(tickers)
    summary["error"] = None

    rebalance_log = pd.concat(rebalance_logs, ignore_index=True)

    strategy_equity = strategy_equity.copy()
    strategy_equity["run_id"] = run_id
    strategy_equity["tickers"] = ticker_string
    strategy_equity["curve_type"] = "market_state"

    equal_weight_rebalance_equity = equal_weight_rebalance_equity.copy()
    equal_weight_rebalance_equity["run_id"] = run_id
    equal_weight_rebalance_equity["tickers"] = ticker_string
    equal_weight_rebalance_equity["curve_type"] = "equal_weight_rebalance"

    equal_weight_buy_hold_equity = equal_weight_buy_hold_equity.copy()
    equal_weight_buy_hold_equity["run_id"] = run_id
    equal_weight_buy_hold_equity["tickers"] = ticker_string
    equal_weight_buy_hold_equity["curve_type"] = "equal_weight_buy_hold"

    equity_curves = pd.concat(
        [
            strategy_equity,
            equal_weight_rebalance_equity,
            equal_weight_buy_hold_equity,
        ],
        axis=0,
    )

    return summary, rebalance_log, equity_curves


def summarize_distribution(
    trials: pd.DataFrame,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    good = trials[trials["error"].isna()].copy()

    if good.empty:
        return pd.DataFrame()

    if columns is None:
        columns = [
            "total_return_pct",
            "cagr_pct",
            "max_drawdown_pct",
            "sharpe",
            "final_equity",
        ]

    rows = []

    for metric in columns:
        if metric not in good.columns:
            continue

        s = pd.to_numeric(good[metric], errors="coerce").dropna()

        if s.empty:
            continue

        rows.append(
            {
                "metric": metric,
                "mean": s.mean(),
                "median": s.median(),
                "std": s.std(ddof=0),
                "min": s.min(),
                "p05": s.quantile(0.05),
                "p25": s.quantile(0.25),
                "p75": s.quantile(0.75),
                "p95": s.quantile(0.95),
                "max": s.max(),
            }
        )

    return pd.DataFrame(rows)


def benchmark_comparison_summary(trials: pd.DataFrame) -> pd.DataFrame:
    good = trials[trials["error"].isna()].copy()

    if good.empty:
        return pd.DataFrame()

    comparison_cols = [
        "excess_return_vs_ew_rebalance_pct",
        "excess_return_vs_ew_buy_hold_pct",
        "drawdown_improvement_vs_ew_rebalance_pct",
        "drawdown_improvement_vs_ew_buy_hold_pct",
        "sharpe_diff_vs_ew_rebalance",
        "sharpe_diff_vs_ew_buy_hold",
    ]

    summary = summarize_distribution(good, columns=comparison_cols)

    win_stats = {
        "metric": "win_rates",
        "mean": np.nan,
        "median": np.nan,
        "std": np.nan,
        "min": np.nan,
        "p05": np.nan,
        "p25": np.nan,
        "p75": np.nan,
        "p95": np.nan,
        "max": np.nan,
    }

    rows = []

    if "beat_ew_rebalance_return" in good.columns:
        rows.append(
            {
                **win_stats,
                "metric": "beat_ew_rebalance_return_pct",
                "mean": good["beat_ew_rebalance_return"].mean() * 100,
            }
        )

    if "beat_ew_buy_hold_return" in good.columns:
        rows.append(
            {
                **win_stats,
                "metric": "beat_ew_buy_hold_return_pct",
                "mean": good["beat_ew_buy_hold_return"].mean() * 100,
            }
        )

    if rows:
        summary = pd.concat([summary, pd.DataFrame(rows)], ignore_index=True)

    return summary


def risk_stats(trials: pd.DataFrame) -> dict:
    good = trials[trials["error"].isna()].copy()

    if good.empty:
        return {
            "successful_runs": 0,
            "failed_runs": len(trials),
        }

    total_return = pd.to_numeric(good["total_return_pct"], errors="coerce")
    max_dd = pd.to_numeric(good["max_drawdown_pct"], errors="coerce")
    sharpe = pd.to_numeric(good["sharpe"], errors="coerce")

    return {
        "successful_runs": int(len(good)),
        "failed_runs": int(trials["error"].notna().sum()),
        "prob_loss_pct": float((total_return < 0).mean() * 100),
        "prob_dd_worse_20_pct": float((max_dd < -20).mean() * 100),
        "prob_dd_worse_30_pct": float((max_dd < -30).mean() * 100),
        "prob_dd_worse_40_pct": float((max_dd < -40).mean() * 100),
        "prob_dd_worse_50_pct": float((max_dd < -50).mean() * 100),
        "prob_sharpe_below_0_pct": float((sharpe < 0).mean() * 100),
        "prob_sharpe_below_1_pct": float((sharpe < 1).mean() * 100),
    }


def plot_histogram(
    trials: pd.DataFrame,
    column: str,
    title: str,
    output_path: Path,
) -> None:
    good = trials[trials["error"].isna()].copy()

    if good.empty or column not in good.columns:
        return

    values = pd.to_numeric(good[column], errors="coerce").dropna()

    if values.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(values, bins=20)
    ax.set_title(title)
    ax.set_xlabel(column)
    ax.set_ylabel("Frequency")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_monte_carlo_equity_curves(
    equity_curves: pd.DataFrame,
    output_path: Path,
    capital: float,
    curve_type: str = "market_state",
) -> None:
    if equity_curves.empty:
        return

    curves = equity_curves[equity_curves["curve_type"] == curve_type].copy()

    if curves.empty:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    curves["date"] = pd.to_datetime(curves["date"])

    fig, ax = plt.subplots(figsize=(12, 7))

    for _, group in curves.groupby("run_id"):
        group = group.sort_values("date")
        ax.plot(
            group["date"],
            group["equity"],
            linewidth=1.0,
            alpha=0.25,
        )

    curve_matrix = curves.pivot_table(
        index="date",
        columns="run_id",
        values="equity",
        aggfunc="last",
    ).sort_index()

    median_curve = curve_matrix.median(axis=1)
    p25_curve = curve_matrix.quantile(0.25, axis=1)
    p75_curve = curve_matrix.quantile(0.75, axis=1)

    ax.plot(
        median_curve.index,
        median_curve.values,
        linewidth=2.5,
        label="Median path",
    )

    ax.plot(
        p25_curve.index,
        p25_curve.values,
        linewidth=1.5,
        linestyle="--",
        label="25th percentile path",
    )

    ax.plot(
        p75_curve.index,
        p75_curve.values,
        linewidth=1.5,
        linestyle="--",
        label="75th percentile path",
    )

    ax.axhline(
        capital,
        linestyle=":",
        linewidth=1.5,
        label="Starting capital",
    )

    ax.set_title(f"Monte Carlo Equity Curves: {curve_type}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_median_benchmark_comparison(
    equity_curves: pd.DataFrame,
    output_path: Path,
    capital: float,
) -> None:
    if equity_curves.empty:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    curves = equity_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"])

    fig, ax = plt.subplots(figsize=(12, 7))

    for curve_type, group in curves.groupby("curve_type"):
        curve_matrix = group.pivot_table(
            index="date",
            columns="run_id",
            values="equity",
            aggfunc="last",
        ).sort_index()

        median_curve = curve_matrix.median(axis=1)

        ax.plot(
            median_curve.index,
            median_curve.values,
            linewidth=2.5,
            label=curve_type,
        )

    ax.axhline(
        capital,
        linestyle=":",
        linewidth=1.5,
        label="Starting capital",
    )

    ax.set_title("Median Monte Carlo Path: Strategy vs Benchmarks")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()

    rng = random.Random(args.seed)

    feature_path = Path(args.feature_path)
    price_path = Path(args.price_path)

    if not feature_path.exists():
        raise FileNotFoundError(f"Feature file not found: {feature_path}")

    if not price_path.exists():
        raise FileNotFoundError(f"Price file not found: {price_path}")

    features = pd.read_csv(feature_path)
    features["date"] = pd.to_datetime(features["date"])

    close_prices = pd.read_csv(price_path, index_col=0, parse_dates=True)

    universe = sorted(features["ticker"].dropna().unique().tolist())

    if args.sample_size > len(universe):
        raise ValueError(
            f"sample-size={args.sample_size} is larger than universe size={len(universe)}"
        )

    output_dir = Path(args.output_dir)
    runs_dir = output_dir / "runs"
    plots_dir = output_dir / "plots"

    if args.save_mode != "none":
        output_dir.mkdir(parents=True, exist_ok=True)

    if args.save_mode == "full":
        runs_dir.mkdir(parents=True, exist_ok=True)

    if args.save_mode in {"curves", "full"}:
        plots_dir.mkdir(parents=True, exist_ok=True)

    print("\nRunning Fast Monte Carlo From Feature Matrix")
    print(f"Feature rows: {len(features)}")
    print(f"Universe size: {len(universe)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {args.sample_size}")
    print(f"Capital: ${args.capital:,.2f}")
    print(f"Max weight: {args.max_weight:.2%}")
    print(f"Seed: {args.seed}")
    print(f"Save mode: {args.save_mode}")

    trial_rows = []
    all_equity_curves = []

    for run_id in range(1, args.runs + 1):
        tickers = sorted(rng.sample(universe, args.sample_size))

        try:
            summary, rebalance_log, equity_curves = run_one_simulation(
                run_id=run_id,
                tickers=tickers,
                features=features,
                close_prices=close_prices,
                capital=args.capital,
                max_weight=args.max_weight,
            )

            trial_rows.append(summary)

            if args.save_mode == "full":
                run_dir = runs_dir / f"run_{run_id:04d}"
                run_dir.mkdir(parents=True, exist_ok=True)

                rebalance_log.to_csv(run_dir / "rebalance_log.csv", index=False)

                equity_curves_out = equity_curves.copy()
                equity_curves_out.index.name = "date"
                equity_curves_out.to_csv(run_dir / "equity_curves.csv")

            if args.save_mode in {"curves", "full"}:
                equity_curves_collect = equity_curves.copy()
                equity_curves_collect.index.name = "date"
                equity_curves_collect = equity_curves_collect.reset_index()
                all_equity_curves.append(equity_curves_collect)

            print(
                f"Run {run_id:04d}: "
                f"strategy={summary['total_return_pct']:.2f}% "
                f"ew_reb={summary['ew_rebalance_total_return_pct']:.2f}% "
                f"buy_hold={summary['ew_buy_hold_total_return_pct']:.2f}% "
                f"excess_ew={summary['excess_return_vs_ew_rebalance_pct']:.2f}% "
                f"dd={summary['max_drawdown_pct']:.2f}% "
                f"sharpe={summary['sharpe']:.2f}"
            )

        except Exception as exc:
            trial_rows.append(
                {
                    "run_id": run_id,
                    "tickers": " ".join(tickers),
                    "num_tickers": len(tickers),
                    "error": str(exc),
                }
            )

            print(f"Run {run_id:04d} failed: {exc}")

    trials = pd.DataFrame(trial_rows)

    if all_equity_curves:
        equity_curves = pd.concat(all_equity_curves, ignore_index=True)
    else:
        equity_curves = pd.DataFrame()

    trials_path = output_dir / "monte_carlo_trials.csv"
    dist_path = output_dir / "monte_carlo_distribution.csv"
    benchmark_dist_path = output_dir / "monte_carlo_benchmark_distribution.csv"
    comparison_path = output_dir / "monte_carlo_benchmark_comparison.csv"
    risk_path = output_dir / "monte_carlo_risk_stats.csv"
    equity_curves_path = output_dir / "monte_carlo_equity_curves.csv"

    distribution = summarize_distribution(trials)

    benchmark_columns = [
        "total_return_pct",
        "ew_rebalance_total_return_pct",
        "ew_buy_hold_total_return_pct",
        "max_drawdown_pct",
        "ew_rebalance_max_drawdown_pct",
        "ew_buy_hold_max_drawdown_pct",
        "sharpe",
        "ew_rebalance_sharpe",
        "ew_buy_hold_sharpe",
    ]

    benchmark_distribution = summarize_distribution(
        trials,
        columns=benchmark_columns,
    )

    comparison = benchmark_comparison_summary(trials)

    risk = risk_stats(trials)
    risk_df = pd.DataFrame([risk])

    if args.save_mode != "none":
        trials.to_csv(trials_path, index=False)
        distribution.to_csv(dist_path, index=False)
        benchmark_distribution.to_csv(benchmark_dist_path, index=False)
        comparison.to_csv(comparison_path, index=False)
        risk_df.to_csv(risk_path, index=False)

    if args.save_mode in {"curves", "full"} and not equity_curves.empty:
        equity_curves.to_csv(equity_curves_path, index=False)

        plot_histogram(
            trials,
            column="total_return_pct",
            title="MarketState Total Return Distribution",
            output_path=plots_dir / "strategy_total_return_hist.png",
        )

        plot_histogram(
            trials,
            column="ew_rebalance_total_return_pct",
            title="Equal-Weight Rebalance Total Return Distribution",
            output_path=plots_dir / "ew_rebalance_total_return_hist.png",
        )

        plot_histogram(
            trials,
            column="ew_buy_hold_total_return_pct",
            title="Equal-Weight Buy-and-Hold Total Return Distribution",
            output_path=plots_dir / "ew_buy_hold_total_return_hist.png",
        )

        plot_histogram(
            trials,
            column="max_drawdown_pct",
            title="MarketState Max Drawdown Distribution",
            output_path=plots_dir / "strategy_max_drawdown_hist.png",
        )

        plot_histogram(
            trials,
            column="sharpe",
            title="MarketState Sharpe Distribution",
            output_path=plots_dir / "strategy_sharpe_hist.png",
        )

        plot_histogram(
            trials,
            column="excess_return_vs_ew_rebalance_pct",
            title="Excess Return vs Equal-Weight Rebalance",
            output_path=plots_dir / "excess_return_vs_ew_rebalance_hist.png",
        )

        plot_monte_carlo_equity_curves(
            equity_curves=equity_curves,
            output_path=plots_dir / "strategy_equity_curves_spaghetti.png",
            capital=args.capital,
            curve_type="market_state",
        )

        plot_monte_carlo_equity_curves(
            equity_curves=equity_curves,
            output_path=plots_dir / "ew_rebalance_equity_curves_spaghetti.png",
            capital=args.capital,
            curve_type="equal_weight_rebalance",
        )

        plot_monte_carlo_equity_curves(
            equity_curves=equity_curves,
            output_path=plots_dir / "ew_buy_hold_equity_curves_spaghetti.png",
            capital=args.capital,
            curve_type="equal_weight_buy_hold",
        )

        plot_median_benchmark_comparison(
            equity_curves=equity_curves,
            output_path=plots_dir / "median_strategy_vs_benchmarks.png",
            capital=args.capital,
        )

    print("\nMonte Carlo Distribution:")
    if distribution.empty:
        print("No successful runs.")
    else:
        print(
            tabulate(
                distribution.round(4),
                headers="keys",
                tablefmt="github",
                showindex=False,
            )
        )

    print("\nBenchmark Distribution:")
    if benchmark_distribution.empty:
        print("No successful runs.")
    else:
        print(
            tabulate(
                benchmark_distribution.round(4),
                headers="keys",
                tablefmt="github",
                showindex=False,
            )
        )

    print("\nBenchmark Comparison:")
    if comparison.empty:
        print("No successful runs.")
    else:
        print(
            tabulate(
                comparison.round(4),
                headers="keys",
                tablefmt="github",
                showindex=False,
            )
        )

    print("\nMonte Carlo Risk Stats:")
    print(
        tabulate(
            risk_df.round(4),
            headers="keys",
            tablefmt="github",
            showindex=False,
        )
    )

    if args.save_mode == "none":
        print("\nSave mode is none; no files written.")
    else:
        print("\nSaved outputs:")
        print(f"  Trials:                  {trials_path}")
        print(f"  Distribution:            {dist_path}")
        print(f"  Benchmark distribution:  {benchmark_dist_path}")
        print(f"  Benchmark comparison:    {comparison_path}")
        print(f"  Risk stats:              {risk_path}")

        if args.save_mode in {"curves", "full"}:
            print(f"  Equity curves:           {equity_curves_path}")
            print(f"  Plots dir:               {plots_dir}")
            print(
                f"  Strategy spaghetti:      {plots_dir / 'strategy_equity_curves_spaghetti.png'}"
            )
            print(
                f"  EW rebalance spaghetti:  {plots_dir / 'ew_rebalance_equity_curves_spaghetti.png'}"
            )
            print(
                f"  EW buy-hold spaghetti:   {plots_dir / 'ew_buy_hold_equity_curves_spaghetti.png'}"
            )
            print(
                f"  Median comparison:       {plots_dir / 'median_strategy_vs_benchmarks.png'}"
            )

        if args.save_mode == "full":
            print(f"  Per-run folders:         {runs_dir}")
    print("\nDone.")


if __name__ == "__main__":
    main()
