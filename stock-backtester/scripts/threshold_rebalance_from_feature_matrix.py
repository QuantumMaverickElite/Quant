from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate


DEFAULT_THRESHOLDS = [0.00, 0.03, 0.05, 0.10, 0.15, 0.20]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monte Carlo threshold-rebalance test from MarketState feature matrix."
    )

    parser.add_argument(
        "--feature-path",
        default="outputs/feature_matrix/rebalance_W/market_state_features.csv",
        help="Feature matrix CSV. Default uses weekly rebalance feature matrix.",
    )

    parser.add_argument(
        "--price-path",
        default="outputs/feature_matrix/rebalance_W/close_prices.csv",
        help="Close prices CSV.",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=1000,
        help="Number of Monte Carlo runs.",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=12,
        help="Number of tickers sampled per Monte Carlo run.",
    )

    parser.add_argument(
        "--portfolio-size",
        type=int,
        default=12,
        help="Number of positions held by the strategy.",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=10_000.0,
        help="Starting capital.",
    )

    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.35,
        help="Maximum position weight.",
    )

    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=DEFAULT_THRESHOLDS,
        help="Score improvement thresholds to test.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact", "curves"],
        default="compact",
        help="none=print only, compact=summary CSVs, curves=compact+equity curve CSV+plots.",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/threshold_rebalance/weekly_check_v1",
        help="Output directory.",
    )

    return parser.parse_args()


def load_features(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str)

    if "adjusted_score" not in df.columns:
        raise ValueError("Feature matrix must contain adjusted_score column.")

    df["adjusted_score"] = pd.to_numeric(df["adjusted_score"], errors="coerce").fillna(0.0)

    return df.sort_values(["date", "ticker"]).reset_index(drop=True)


def load_prices(path: str | Path) -> pd.DataFrame:
    prices = pd.read_csv(path)

    first_col = prices.columns[0]
    prices[first_col] = pd.to_datetime(prices[first_col])
    prices = prices.rename(columns={first_col: "date"}).set_index("date").sort_index()

    for col in prices.columns:
        prices[col] = pd.to_numeric(prices[col], errors="coerce")

    return prices


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min() * 100.0)


def sharpe_ratio(equity: pd.Series) -> float:
    returns = equity.pct_change().dropna()

    if returns.empty:
        return 0.0

    std = returns.std(ddof=0)

    if std == 0 or pd.isna(std):
        return 0.0

    return float((returns.mean() / std) * np.sqrt(252))


def cagr(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0

    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])

    if start <= 0:
        return 0.0

    days = max((equity.index[-1] - equity.index[0]).days, 1)
    years = days / 365.25

    return float(((end / start) ** (1.0 / years) - 1.0) * 100.0)


def summarize_equity(equity: pd.Series, capital: float) -> dict[str, float]:
    final_equity = float(equity.iloc[-1])
    total_return_pct = (final_equity / capital - 1.0) * 100.0

    return {
        "final_equity": final_equity,
        "total_return_pct": float(total_return_pct),
        "cagr_pct": cagr(equity),
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


def get_price_row(prices: pd.DataFrame, date: pd.Timestamp) -> pd.Series:
    if date in prices.index:
        return prices.loc[date]

    idx = prices.index.searchsorted(date, side="right") - 1

    if idx < 0:
        raise ValueError(f"No price row available on or before {date}")

    return prices.iloc[idx]


def select_candidate(
    features_on_date: pd.DataFrame,
    tickers: list[str],
    portfolio_size: int,
) -> list[str]:
    sub = features_on_date[features_on_date["ticker"].isin(tickers)].copy()

    if sub.empty:
        return []

    sub = sub.sort_values(
        ["adjusted_score", "ticker"],
        ascending=[False, True],
    )

    return sub.head(portfolio_size)["ticker"].tolist()


def average_score(
    features_on_date: pd.DataFrame,
    holdings: list[str],
) -> float:
    if not holdings:
        return 0.0

    sub = features_on_date[features_on_date["ticker"].isin(holdings)]

    if sub.empty:
        return 0.0

    score_by_ticker = sub.set_index("ticker")["adjusted_score"].to_dict()
    scores = [float(score_by_ticker.get(ticker, 0.0)) for ticker in holdings]

    return float(np.mean(scores)) if scores else 0.0


def rebalance_to_holdings(
    holdings: list[str],
    equity_value: float,
    price_row: pd.Series,
    max_weight: float,
) -> tuple[dict[str, float], float]:
    if not holdings:
        return {}, equity_value

    raw_weight = 1.0 / len(holdings)
    position_weight = min(raw_weight, max_weight)

    shares: dict[str, float] = {}
    invested = 0.0

    for ticker in holdings:
        price = float(price_row.get(ticker, np.nan))

        if not np.isfinite(price) or price <= 0:
            continue

        dollars = equity_value * position_weight
        shares[ticker] = dollars / price
        invested += dollars

    cash = max(equity_value - invested, 0.0)

    return shares, cash


def portfolio_value(
    shares: dict[str, float],
    cash: float,
    price_row: pd.Series,
) -> float:
    value = float(cash)

    for ticker, qty in shares.items():
        price = float(price_row.get(ticker, np.nan))

        if np.isfinite(price) and price > 0:
            value += qty * price

    return float(value)


def run_threshold_backtest(
    features: pd.DataFrame,
    prices: pd.DataFrame,
    tickers: list[str],
    threshold: float,
    capital: float,
    portfolio_size: int,
    max_weight: float,
) -> tuple[pd.Series, pd.DataFrame]:
    check_dates = sorted(features["date"].dropna().unique())
    check_dates = [pd.Timestamp(date) for date in check_dates]

    if not check_dates:
        raise ValueError("No check dates found in feature matrix.")

    price_dates = prices.index[
        (prices.index >= check_dates[0]) & (prices.index <= check_dates[-1])
    ]

    if price_dates.empty:
        raise ValueError("No price dates overlap the feature matrix dates.")

    feature_by_date = {
        pd.Timestamp(date): group.copy()
        for date, group in features.groupby("date", sort=True)
    }

    equity_value = capital
    shares: dict[str, float] = {}
    cash = capital
    holdings: list[str] = []

    equity_rows = []
    rebalance_rows = []

    check_date_set = set(check_dates)

    for date in price_dates:
        price_row = get_price_row(prices, pd.Timestamp(date))

        equity_value = portfolio_value(shares, cash, price_row)

        if pd.Timestamp(date) in check_date_set:
            fdate = feature_by_date[pd.Timestamp(date)]

            candidate = select_candidate(
                features_on_date=fdate,
                tickers=tickers,
                portfolio_size=portfolio_size,
            )

            current_score = average_score(fdate, holdings)
            candidate_score = average_score(fdate, candidate)
            improvement = candidate_score - current_score

            should_rebalance = False
            reason = "hold"

            if not holdings:
                should_rebalance = True
                reason = "initial"
            elif improvement >= threshold:
                should_rebalance = True
                reason = "threshold_met"

            if should_rebalance:
                old_holdings = set(holdings)
                new_holdings = set(candidate)

                if old_holdings:
                    changed = old_holdings.symmetric_difference(new_holdings)
                    turnover_count = len(changed)
                    turnover_pct = turnover_count / max(len(old_holdings.union(new_holdings)), 1) * 100.0
                else:
                    turnover_count = len(new_holdings)
                    turnover_pct = 100.0

                holdings = candidate
                shares, cash = rebalance_to_holdings(
                    holdings=holdings,
                    equity_value=equity_value,
                    price_row=price_row,
                    max_weight=max_weight,
                )

                equity_value = portfolio_value(shares, cash, price_row)

                rebalance_rows.append(
                    {
                        "date": pd.Timestamp(date),
                        "reason": reason,
                        "threshold": threshold,
                        "current_score": current_score,
                        "candidate_score": candidate_score,
                        "improvement": improvement,
                        "holdings": ",".join(holdings),
                        "turnover_count": turnover_count,
                        "turnover_pct": turnover_pct,
                        "equity": equity_value,
                    }
                )

        equity_rows.append({"date": pd.Timestamp(date), "equity": equity_value})

    equity = pd.DataFrame(equity_rows).set_index("date")["equity"]
    rebalance_log = pd.DataFrame(rebalance_rows)

    return equity, rebalance_log


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

        ax.plot(
            median_curve.index,
            median_curve.values,
            linewidth=2.5,
            label="Median path",
        )

        ax.plot(
            p25_curve.index,
            p25_curve.values,
            linestyle="--",
            linewidth=2.0,
            label="25th percentile path",
        )

        ax.plot(
            p75_curve.index,
            p75_curve.values,
            linestyle="--",
            linewidth=2.0,
            label="75th percentile path",
        )

        ax.axhline(10_000, linestyle=":", linewidth=1.5, label="Starting capital")

        ax.set_title(f"Threshold Rebalance Spaghetti: threshold={threshold}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Equity")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        label = str(threshold).replace(".", "p")
        fig.savefig(
            spaghetti_dir / f"threshold_{label}_spaghetti.png",
            dpi=150,
            bbox_inches="tight",
        )
        plt.close(fig)


def main() -> None:
    args = parse_args()

    features = load_features(args.feature_path)
    prices = load_prices(args.price_path)

    universe = sorted(set(features["ticker"]).intersection(prices.columns))

    if not universe:
        raise SystemExit("No overlapping tickers between features and prices.")

    rng = np.random.default_rng(args.seed)

    out_dir = Path(args.output_dir)

    if args.save_mode != "none":
        out_dir.mkdir(parents=True, exist_ok=True)

    print("\nThreshold Rebalance Monte Carlo")
    print(f"Feature rows: {len(features)}")
    print(f"Universe size: {len(universe)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {args.sample_size}")
    print(f"Portfolio size: {args.portfolio_size}")
    print(f"Capital: ${args.capital:,.2f}")
    print(f"Max weight: {args.max_weight:.2%}")
    print(f"Thresholds: {args.thresholds}")
    print(f"Save mode: {args.save_mode}")

    sample_size = min(args.sample_size, len(universe))

    run_samples = [
        sorted(
            rng.choice(
                universe,
                size=sample_size,
                replace=False,
            ).tolist()
        )
        for _ in range(args.runs)
    ]

    trial_rows = []
    rebalance_rows = []
    equity_curve_rows = []

    for threshold in args.thresholds:
        print(f"\n=== Threshold {threshold:.4f} ===")

        for run_id, sampled in enumerate(run_samples, start=1):

            equity, rebalance_log = run_threshold_backtest(
                features=features[features["ticker"].isin(sampled)],
                prices=prices[sampled],
                tickers=sampled,
                threshold=threshold,
                capital=args.capital,
                portfolio_size=min(args.portfolio_size, len(sampled)),
                max_weight=args.max_weight,
            )

            metrics = summarize_equity(equity, args.capital)

            n_rebalances = int(len(rebalance_log))
            mean_turnover = (
                float(rebalance_log["turnover_pct"].mean())
                if not rebalance_log.empty and "turnover_pct" in rebalance_log.columns
                else 0.0
            )

            row = {
                "threshold": threshold,
                "run_id": run_id,
                "tickers": ",".join(sampled),
                "n_rebalances": n_rebalances,
                "mean_turnover_pct": mean_turnover,
                **metrics,
            }

            trial_rows.append(row)

            if not rebalance_log.empty:
                temp_log = rebalance_log.copy()
                temp_log["run_id"] = run_id
                temp_log["threshold"] = threshold
                rebalance_rows.append(temp_log)

            if args.save_mode == "curves":
                temp_curve = equity.reset_index()
                temp_curve["threshold"] = threshold
                temp_curve["run_id"] = run_id
                equity_curve_rows.append(temp_curve)

            print(
                f"threshold={threshold:.4f} run={run_id:04d} "
                f"return={metrics['total_return_pct']:.2f}% "
                f"dd={metrics['max_drawdown_pct']:.2f}% "
                f"sharpe={metrics['sharpe']:.2f} "
                f"rebalances={n_rebalances}"
            )

    trials = pd.DataFrame(trial_rows)

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

        metric_map = {
            row["metric"]: row
            for _, row in dist.iterrows()
        }

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

    summary = pd.DataFrame(summary_rows).sort_values("threshold")

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

        if rebalance_rows:
            rebalance_log = pd.concat(rebalance_rows, ignore_index=True)
            rebalance_path = out_dir / "threshold_rebalance_log.csv"
            rebalance_log.to_csv(rebalance_path, index=False)
            print(f"Saved: {rebalance_path}")

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
