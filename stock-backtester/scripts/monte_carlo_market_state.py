from __future__ import annotations

import argparse
import random
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate

from backtest_market_state_portfolio import run_backtest

DEFAULT_VOLATILE_UNIVERSE = [
    "QBTS",
    "RGTI",
    "IONQ",
    "QUBT",
    "OKLO",
    "SMR",
    "RKLB",
    "ACHR",
    "JOBY",
    "SOUN",
    "AI",
    "MSTR",
    "COIN",
    "MARA",
    "RIOT",
    "CLSK",
    "HUT",
    "BITF",
    "HOOD",
    "UPST",
    "AFRM",
    "CVNA",
    "RIVN",
    "LCID",
    "TSLA",
    "PLTR",
    "SMCI",
    "ARM",
    "NVDA",
    "AMD",
    "MU",
    "APP",
]

DEFAULT_LEVERAGED_UNIVERSE = [
    "TQQQ",
    "SQQQ",
    "SOXL",
    "SOXS",
    "TECL",
    "TECS",
    "FNGU",
    "FNGD",
    "LABU",
    "LABD",
    "NVDL",
    "NVDQ",
    "TSLL",
    "TSLQ",
    "MSTX",
    "MSTZ",
    "CONL",
    "QBTS",
    "RGTI",
    "IONQ",
    "OKLO",
    "RKLB",
    "MSTR",
    "COIN",
    "MARA",
    "RIOT",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monte Carlo test MarketState allocator across random ticker universes."
    )

    parser.add_argument(
        "--universe",
        nargs="+",
        default=DEFAULT_VOLATILE_UNIVERSE,
        help="Full ticker universe to sample from.",
    )

    parser.add_argument(
        "--preset",
        choices=["volatile", "leveraged"],
        default=None,
        help="Optional preset universe.",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=25,
        help="Number of Monte Carlo runs. Default: 25",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=12,
        help="Number of tickers per random basket. Default: 12",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed. Default: 42",
    )

    parser.add_argument(
        "--data-start",
        default="2018-01-01",
        help="Data start date for indicators. Default: 2018-01-01",
    )

    parser.add_argument(
        "--bt-start",
        default="2025-01-01",
        help="Backtest start date. Default: 2025-01-01",
    )

    parser.add_argument(
        "--bt-end",
        default="2026-01-01",
        help="Backtest end date. Default: 2026-01-01",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=10_000.0,
        help="Initial capital. Default: 10000",
    )

    parser.add_argument(
        "--rebalance",
        choices=["D", "W", "B", "3W", "M", "6W", "Q"],
        default="M",
        help=(
            "Rebalance frequency: D=daily, W=weekly, B=bi-weekly, 3W=every 3 weeks, M=monthly, 6W=every 6 weeks, Q=quarterly. "
            "Default: M"
        ),
    )

    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.35,
        help="Maximum weight per ticker. Default: 0.35",
    )

    parser.add_argument(
        "--entropy-window",
        type=int,
        default=60,
        help="Rolling entropy window. Default: 60",
    )

    parser.add_argument(
        "--zscore-window",
        type=int,
        default=252,
        help="Rolling entropy percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of entropy bins. Default: 10",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/monte_carlo/market_state_v1",
        help="Output directory.",
    )

    parser.add_argument(
        "--save-mode",
        choices=["none", "compact", "curves", "full"],
        default="compact",
        help=(
            "Output mode. none=print only, compact=summary CSVs only, "
            "curves=compact+histogram plots, full=curves+per-run folders. "
            "Default: compact"
        ),
    )

    return parser.parse_args()


def choose_universe(args: argparse.Namespace) -> list[str]:
    if args.preset == "volatile":
        return DEFAULT_VOLATILE_UNIVERSE.copy()

    if args.preset == "leveraged":
        return DEFAULT_LEVERAGED_UNIVERSE.copy()

    return [ticker.upper() for ticker in args.universe]


def make_backtest_args(
    tickers: list[str],
    args: argparse.Namespace,
    run_output_dir: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        tickers=tickers,
        data_start=args.data_start,
        bt_start=args.bt_start,
        bt_end=args.bt_end,
        capital=args.capital,
        rebalance=args.rebalance,
        max_weight=args.max_weight,
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        bins=args.bins,
        output_dir=str(run_output_dir),
        save_mode="none",
    )


def summarize_distribution(trials: pd.DataFrame) -> pd.DataFrame:
    good = trials[trials["error"].isna()].copy()

    if good.empty:
        return pd.DataFrame()

    metrics = [
        "total_return_pct",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "final_equity",
    ]

    rows = []

    for metric in metrics:
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


def main() -> None:
    args = parse_args()

    rng = random.Random(args.seed)

    universe = choose_universe(args)
    universe = sorted(set(ticker.upper() for ticker in universe))

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

    print("\nRunning MarketState Universe Monte Carlo")
    print(f"Universe size: {len(universe)}")
    print(f"Runs: {args.runs}")
    print(f"Sample size: {args.sample_size}")
    print(f"Backtest: {args.bt_start} to {args.bt_end}")
    print(f"Capital: ${args.capital:,.2f}")
    print(f"Rebalance: {args.rebalance}")
    print(f"Max weight: {args.max_weight:.2%}")
    print(f"Seed: {args.seed}")
    print(f"Save mode: {args.save_mode}")

    rows = []

    for run_id in range(1, args.runs + 1):
        tickers = sorted(rng.sample(universe, args.sample_size))

        print("\n" + "=" * 80)
        print(f"Monte Carlo run {run_id}/{args.runs}")
        print("Tickers:", ", ".join(tickers))

        run_output_dir = runs_dir / f"run_{run_id:04d}"

        bt_args = make_backtest_args(
            tickers=tickers,
            args=args,
            run_output_dir=run_output_dir,
        )

        try:
            equity_curve, rebalance_log, summary = run_backtest(bt_args)

            if args.save_mode == "full":
                equity_path = run_output_dir / "equity_curve.csv"
                log_path = run_output_dir / "rebalance_log.csv"
                summary_path = run_output_dir / "summary.csv"

                run_output_dir.mkdir(parents=True, exist_ok=True)
                equity_curve.to_csv(equity_path)
                rebalance_log.to_csv(log_path, index=False)
                pd.DataFrame([summary]).to_csv(summary_path, index=False)

            row = {
                "run_id": run_id,
                "tickers": " ".join(tickers),
                "num_tickers": len(tickers),
                "error": None,
                **summary,
            }

            rows.append(row)

            print("\nRun Summary:")
            print(
                tabulate(
                    pd.DataFrame([summary]).round(4),
                    headers="keys",
                    tablefmt="github",
                    showindex=False,
                )
            )

        except Exception as exc:
            print(f"Run failed: {exc}")

            rows.append(
                {
                    "run_id": run_id,
                    "tickers": " ".join(tickers),
                    "num_tickers": len(tickers),
                    "error": str(exc),
                }
            )

    trials = pd.DataFrame(rows)

    trials_path = output_dir / "monte_carlo_trials.csv"
    dist_path = output_dir / "monte_carlo_distribution.csv"
    risk_path = output_dir / "monte_carlo_risk_stats.csv"

    distribution = summarize_distribution(trials)

    risk = risk_stats(trials)
    risk_df = pd.DataFrame([risk])

    if args.save_mode != "none":
        trials.to_csv(trials_path, index=False)
        distribution.to_csv(dist_path, index=False)
        risk_df.to_csv(risk_path, index=False)

    if args.save_mode in {"curves", "full"}:
        plot_histogram(
            trials,
            column="total_return_pct",
            title="Monte Carlo Total Return Distribution",
            output_path=plots_dir / "total_return_hist.png",
        )

        plot_histogram(
            trials,
            column="max_drawdown_pct",
            title="Monte Carlo Max Drawdown Distribution",
            output_path=plots_dir / "max_drawdown_hist.png",
        )

        plot_histogram(
            trials,
            column="sharpe",
            title="Monte Carlo Sharpe Distribution",
            output_path=plots_dir / "sharpe_hist.png",
        )

    print("\n" + "=" * 80)
    print("Monte Carlo Distribution:")
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
        print(f"  Trials:        {trials_path}")
        print(f"  Distribution:  {dist_path}")
        print(f"  Risk stats:    {risk_path}")

        if args.save_mode in {"curves", "full"}:
            print(f"  Plots dir:     {plots_dir}")

        if args.save_mode == "full":
            print(f"  Per-run folders: {runs_dir}")

    print("\nDone.")


if __name__ == "__main__":
    main()
