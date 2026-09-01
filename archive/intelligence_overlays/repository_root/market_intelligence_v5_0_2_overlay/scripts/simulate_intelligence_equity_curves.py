from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


BASELINE_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)

HEURISTIC_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_intelligence_adjusted",
    "adjusted_confidence_intelligence_adjusted",
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)

ML_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_walk_forward_ml_adjusted",
    "allocator_confidence_ml_intelligence_adjusted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate baseline vs intelligence ML equity curves with bootstrap spaghetti plots.")
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--config")
    parser.add_argument("--ranked-summary", type=Path)
    parser.add_argument("--return-col", default="next_5d_return")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--block-size", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--heuristic-confidence-col")
    parser.add_argument("--ml-confidence-col")
    parser.add_argument("--spaghetti-paths", type=int, default=100)
    return parser.parse_args()


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path}")


def write_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
    else:
        raise ValueError(f"Unsupported file type: {path}")


def detect_col(df: pd.DataFrame, requested: str | None, candidates: tuple[str, ...], label: str) -> str:
    if requested:
        if requested not in df.columns:
            raise ValueError(f"{label} column not found: {requested}")
        return requested
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Could not detect {label} column. Tried: {', '.join(candidates)}")


def detect_ticker_col(df: pd.DataFrame, requested: str | None) -> str:
    return detect_col(df, requested, ("ticker", "query", "symbol"), "ticker")


def detect_date_col(df: pd.DataFrame, requested: str | None) -> str:
    return detect_col(df, requested, ("date", "signal_date", "as_of", "timestamp"), "date")


def choose_predictions_path(args: argparse.Namespace) -> Path:
    if args.predictions:
        return args.predictions
    if not args.run_dir:
        raise SystemExit("Provide --predictions or --run-dir.")

    config = args.config
    if not config:
        ranked = args.ranked_summary or args.run_dir / "all_monte_carlo_ranked.csv"
        if not ranked.exists():
            raise SystemExit("Provide --config or --ranked-summary when no ranked summary exists.")
        ranked_df = pd.read_csv(ranked)
        focus = ranked_df.copy()
        if "return_col" in focus.columns:
            focus = focus[focus["return_col"].eq(args.return_col)]
        if "top_n" in focus.columns:
            focus = focus[focus["top_n"].eq(args.top_n)]
        if focus.empty:
            raise SystemExit("No matching config in ranked summary.")
        focus = focus.sort_values(
            [col for col in ("cash_ml_minus_baseline", "prob_ml_beats_baseline") if col in focus.columns],
            ascending=False,
        )
        config = str(focus.iloc[0]["config"])

    path = args.run_dir / f"{config}_predictions.parquet"
    if not path.exists():
        raise SystemExit(f"Predictions file not found: {path}")
    return path


def max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return np.nan
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return float(np.nanmin(dd))


def per_date_portfolio_returns(
    df: pd.DataFrame,
    *,
    date_col: str,
    ticker_col: str,
    return_col: str,
    top_n: int,
    rank_cols: dict[str, str],
) -> pd.DataFrame:
    data = df.copy()
    data["_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data["_return"] = pd.to_numeric(data[return_col], errors="coerce")
    data = data.dropna(subset=["_date", "_return"])
    rows: list[dict] = []
    for date_value, day in data.groupby("_date", sort=True):
        row: dict[str, object] = {"date": date_value}
        for name, rank_col in rank_cols.items():
            picks = day.sort_values(rank_col, ascending=False).drop_duplicates(ticker_col).head(top_n)
            row[f"{name}_return"] = float(picks["_return"].mean()) if len(picks) else np.nan
            row[f"{name}_count"] = int(len(picks))
            row[f"{name}_tickers"] = ",".join(str(x) for x in picks[ticker_col].tolist())
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("date")
    return out


def deterministic_equity(returns: pd.DataFrame, *, cash: float) -> pd.DataFrame:
    out = returns.copy()
    for name in ("baseline", "heuristic_nlp", "walk_forward_ml"):
        col = f"{name}_return"
        if col not in out.columns:
            continue
        values = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        out[f"{name}_equity"] = cash * (1.0 + values).cumprod()
        out[f"{name}_drawdown"] = out[f"{name}_equity"] / out[f"{name}_equity"].cummax() - 1.0
    return out


def bootstrap_indices(rng: np.random.Generator, n_steps: int, iterations: int, block_size: int) -> np.ndarray:
    if n_steps <= 0:
        return np.empty((0, 0), dtype=int)
    if block_size <= 1:
        return rng.integers(0, n_steps, size=(iterations, n_steps))
    starts = rng.integers(0, n_steps, size=(iterations, int(np.ceil(n_steps / block_size))))
    paths = []
    for row in starts:
        idx = []
        for start in row:
            idx.extend((start + np.arange(block_size)).tolist())
        paths.append(np.asarray(idx[:n_steps]) % n_steps)
    return np.vstack(paths)


def bootstrap_equity_paths(returns: pd.DataFrame, *, cash: float, iterations: int, block_size: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n_steps = len(returns)
    if n_steps <= 0:
        return pd.DataFrame(), pd.DataFrame()
    idx = bootstrap_indices(rng, n_steps=n_steps, iterations=iterations, block_size=block_size)
    sim_rows: list[pd.DataFrame] = []
    summary_rows: list[dict] = []

    return_arrays = {
        name: pd.to_numeric(returns[f"{name}_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        for name in ("baseline", "heuristic_nlp", "walk_forward_ml")
        if f"{name}_return" in returns.columns
    }

    for sim in range(iterations):
        row: dict[str, float | int] = {"simulation": sim}
        path_frame = {"simulation": np.full(n_steps, sim, dtype=int), "step": np.arange(1, n_steps + 1, dtype=int)}
        for name, arr in return_arrays.items():
            sampled = arr[idx[sim]]
            equity = cash * np.cumprod(1.0 + sampled)
            path_frame[f"{name}_equity"] = equity
            row[f"{name}_ending_equity"] = float(equity[-1])
            row[f"{name}_total_return"] = float(equity[-1] / cash - 1.0)
            row[f"{name}_max_drawdown"] = max_drawdown(equity)
        if "baseline" in return_arrays and "walk_forward_ml" in return_arrays:
            row["ml_minus_baseline_ending_cash"] = row["walk_forward_ml_ending_equity"] - row["baseline_ending_equity"]
            row["ml_beats_baseline"] = float(row["walk_forward_ml_ending_equity"] > row["baseline_ending_equity"])
            row["ml_nonworse_baseline"] = float(row["walk_forward_ml_ending_equity"] >= row["baseline_ending_equity"])
            row["ml_drawdown_better_baseline"] = float(row["walk_forward_ml_max_drawdown"] > row["baseline_max_drawdown"])
        if "heuristic_nlp" in return_arrays and "walk_forward_ml" in return_arrays:
            row["ml_minus_heuristic_ending_cash"] = row["walk_forward_ml_ending_equity"] - row["heuristic_nlp_ending_equity"]
            row["ml_beats_heuristic"] = float(row["walk_forward_ml_ending_equity"] > row["heuristic_nlp_ending_equity"])
        summary_rows.append(row)
        sim_rows.append(pd.DataFrame(path_frame))

    paths = pd.concat(sim_rows, ignore_index=True) if sim_rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return paths, summary


def summarize_simulations(summary: pd.DataFrame, deterministic: pd.DataFrame, *, cash: float) -> pd.DataFrame:
    rows: list[dict] = []
    for name in ("baseline", "heuristic_nlp", "walk_forward_ml"):
        ending_col = f"{name}_ending_equity"
        dd_col = f"{name}_max_drawdown"
        if ending_col not in summary.columns:
            continue
        rows.append(
            {
                "ranking": name,
                "deterministic_ending_equity": float(deterministic[f"{name}_equity"].iloc[-1]) if f"{name}_equity" in deterministic.columns and len(deterministic) else np.nan,
                "deterministic_total_return": float(deterministic[f"{name}_equity"].iloc[-1] / cash - 1.0) if f"{name}_equity" in deterministic.columns and len(deterministic) else np.nan,
                "deterministic_max_drawdown": float(deterministic[f"{name}_drawdown"].min()) if f"{name}_drawdown" in deterministic.columns and len(deterministic) else np.nan,
                "ending_equity_p05": float(summary[ending_col].quantile(0.05)),
                "ending_equity_p50": float(summary[ending_col].quantile(0.50)),
                "ending_equity_p95": float(summary[ending_col].quantile(0.95)),
                "max_drawdown_p50": float(summary[dd_col].quantile(0.50)) if dd_col in summary.columns else np.nan,
                "max_drawdown_p05": float(summary[dd_col].quantile(0.05)) if dd_col in summary.columns else np.nan,
            }
        )

    comparison = {
        "ranking": "ml_vs_baseline",
        "prob_ml_beats_baseline": float(summary["ml_beats_baseline"].mean()) if "ml_beats_baseline" in summary.columns else np.nan,
        "prob_ml_nonworse_baseline": float(summary["ml_nonworse_baseline"].mean()) if "ml_nonworse_baseline" in summary.columns else np.nan,
        "prob_ml_drawdown_better_baseline": float(summary["ml_drawdown_better_baseline"].mean()) if "ml_drawdown_better_baseline" in summary.columns else np.nan,
        "ml_minus_baseline_ending_cash_p05": float(summary["ml_minus_baseline_ending_cash"].quantile(0.05)) if "ml_minus_baseline_ending_cash" in summary.columns else np.nan,
        "ml_minus_baseline_ending_cash_p50": float(summary["ml_minus_baseline_ending_cash"].quantile(0.50)) if "ml_minus_baseline_ending_cash" in summary.columns else np.nan,
        "ml_minus_baseline_ending_cash_p95": float(summary["ml_minus_baseline_ending_cash"].quantile(0.95)) if "ml_minus_baseline_ending_cash" in summary.columns else np.nan,
    }
    rows.append(comparison)
    return pd.DataFrame(rows)


def write_plots(
    deterministic: pd.DataFrame,
    paths: pd.DataFrame,
    summary: pd.DataFrame,
    out_dir: Path,
    *,
    spaghetti_paths: int,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable; skipped plots: {exc}")
        return

    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    colors = {"baseline": "tab:blue", "heuristic_nlp": "tab:orange", "walk_forward_ml": "tab:green"}

    plt.figure(figsize=(11, 6))
    for name, color in colors.items():
        col = f"{name}_equity"
        if col in deterministic.columns:
            plt.plot(deterministic["date"], deterministic[col], label=name, color=color)
    plt.title("Deterministic Equity Curve")
    plt.xlabel("date")
    plt.ylabel("equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "deterministic_equity.png", dpi=150)
    plt.close()

    if not paths.empty:
        sims = sorted(paths["simulation"].drop_duplicates().head(spaghetti_paths).tolist())
        plt.figure(figsize=(11, 6))
        for name, color in colors.items():
            col = f"{name}_equity"
            if col not in paths.columns:
                continue
            for sim in sims:
                part = paths[paths["simulation"].eq(sim)]
                plt.plot(part["step"], part[col], color=color, alpha=0.08, linewidth=0.8)
        for name, color in colors.items():
            col = f"{name}_equity"
            if col in paths.columns:
                median = paths.groupby("step")[col].median()
                plt.plot(median.index, median.values, color=color, linewidth=2.0, label=f"{name} median")
        plt.title("Bootstrap Equity Spaghetti")
        plt.xlabel("sampled test step")
        plt.ylabel("equity")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_dir / "bootstrap_spaghetti.png", dpi=150)
        plt.close()

    if "ml_minus_baseline_ending_cash" in summary.columns:
        hist_values = pd.to_numeric(summary["ml_minus_baseline_ending_cash"], errors="coerce")
        hist_values = hist_values[np.isfinite(hist_values)]
        if hist_values.empty:
            print("Skipped ML-minus-baseline histogram: no finite values.")
            return
        plt.figure(figsize=(10, 5))
        bins = 1 if hist_values.nunique(dropna=True) <= 1 else min(40, max(5, int(np.sqrt(len(hist_values)))))
        plt.hist(hist_values, bins=bins, color="tab:green", alpha=0.75)
        plt.axvline(0, color="black", linewidth=1.0)
        plt.title("ML Minus Baseline Ending Cash Distribution")
        plt.xlabel("ending cash difference")
        plt.ylabel("simulation count")
        plt.tight_layout()
        plt.savefig(plots_dir / "ml_minus_baseline_distribution.png", dpi=150)
        plt.close()


def main() -> None:
    args = parse_args()
    predictions_path = choose_predictions_path(args)
    predictions = read_table(predictions_path)
    if predictions.empty:
        raise SystemExit(f"Predictions file has zero rows: {predictions_path}")
    ticker_col = detect_ticker_col(predictions, args.ticker_col)
    date_col = detect_date_col(predictions, args.date_col)
    baseline_col = detect_col(predictions, args.baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline confidence")
    heuristic_col = detect_col(predictions, args.heuristic_confidence_col, HEURISTIC_CONFIDENCE_CANDIDATES, "heuristic confidence")
    ml_col = detect_col(predictions, args.ml_confidence_col, ML_CONFIDENCE_CANDIDATES, "ML confidence")
    rank_cols = {"baseline": baseline_col, "heuristic_nlp": heuristic_col, "walk_forward_ml": ml_col}

    returns = per_date_portfolio_returns(
        predictions,
        date_col=date_col,
        ticker_col=ticker_col,
        return_col=args.return_col,
        top_n=args.top_n,
        rank_cols=rank_cols,
    )
    deterministic = deterministic_equity(returns, cash=args.cash)
    paths, sim_summary = bootstrap_equity_paths(
        returns,
        cash=args.cash,
        iterations=args.iterations,
        block_size=args.block_size,
        seed=args.seed,
    )
    summary = summarize_simulations(sim_summary, deterministic, cash=args.cash)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_table(returns, args.out_dir / "portfolio_returns.csv")
    write_table(deterministic, args.out_dir / "deterministic_equity.csv")
    write_table(paths, args.out_dir / "bootstrap_equity_paths.csv")
    write_table(sim_summary, args.out_dir / "bootstrap_summary.csv")
    write_table(summary, args.out_dir / "equity_simulation_summary.csv")
    write_plots(deterministic, paths, sim_summary, args.out_dir, spaghetti_paths=args.spaghetti_paths)

    print(f"Predictions: {predictions_path}")
    print(f"Saved outputs: {args.out_dir}")
    print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
