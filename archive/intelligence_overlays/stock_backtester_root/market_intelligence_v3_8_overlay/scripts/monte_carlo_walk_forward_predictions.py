from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.candidates import detect_date_column, detect_ticker_column, read_table, write_table
from backtester.intelligence.walk_forward_calibrator import (
    BASELINE_CONFIDENCE_CANDIDATES,
    HEURISTIC_CONFIDENCE_CANDIDATES,
    resolve_confidence_column,
)


ML_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_walk_forward_ml_adjusted",
    "allocator_confidence_ml_intelligence_adjusted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Monte Carlo tests for walk-forward intelligence predictions.")
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--simulations-out", type=Path)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--heuristic-confidence-col")
    parser.add_argument("--ml-confidence-col")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _resolve_ml_column(df: pd.DataFrame, requested: str | None) -> str:
    if requested:
        if requested not in df.columns:
            raise ValueError(f"ML confidence column not found: {requested}")
        return requested
    for col in ML_CONFIDENCE_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(f"Could not detect ML confidence column. Tried: {', '.join(ML_CONFIDENCE_CANDIDATES)}")


def _drawdown_col(df: pd.DataFrame, return_col: str) -> str | None:
    if return_col.startswith("next_") and return_col.endswith("_return"):
        middle = return_col.removeprefix("next_").removesuffix("_return")
        candidate = f"max_drawdown_next_{middle}"
        if candidate in df.columns:
            return candidate
    for candidate in ("max_drawdown_next_10d", "max_drawdown_next_20d", "max_drawdown_next_5d"):
        if candidate in df.columns:
            return candidate
    return None


def _date_rank_metrics(
    day: pd.DataFrame,
    *,
    ticker_col: str,
    rank_col: str,
    return_col: str,
    top_n: int,
    drawdown_col: str | None,
) -> dict[str, float]:
    picks = day.sort_values(rank_col, ascending=False).drop_duplicates(ticker_col).head(top_n).copy()
    returns = pd.to_numeric(picks[return_col], errors="coerce")
    out = {
        "mean_return": float(returns.mean()) if len(returns) else np.nan,
        "hit_rate": float((returns > 0).mean()) if len(returns) else np.nan,
        "selection_count": float(len(picks)),
    }
    if drawdown_col and drawdown_col in picks.columns:
        out["avg_drawdown"] = float(pd.to_numeric(picks[drawdown_col], errors="coerce").mean())
    return out


def per_date_metrics(
    df: pd.DataFrame,
    *,
    date_col: str,
    ticker_col: str,
    return_col: str,
    top_n: int,
    rank_cols: dict[str, str],
) -> pd.DataFrame:
    drawdown_col = _drawdown_col(df, return_col)
    rows: list[dict] = []
    data = df.copy()
    data["_mc_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=["_mc_date"])
    for date_value, day in data.groupby("_mc_date"):
        row: dict[str, float | str] = {"date": date_value}
        for name, rank_col in rank_cols.items():
            metrics = _date_rank_metrics(
                day,
                ticker_col=ticker_col,
                rank_col=rank_col,
                return_col=return_col,
                top_n=top_n,
                drawdown_col=drawdown_col,
            )
            for metric, value in metrics.items():
                row[f"{name}_{metric}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(
    metrics: pd.DataFrame,
    *,
    iterations: int,
    rng: np.random.Generator,
    cash: float,
) -> tuple[dict, pd.DataFrame]:
    if metrics.empty:
        return {}, pd.DataFrame()
    n_dates = len(metrics)
    baseline = metrics["baseline_mean_return"].to_numpy(dtype=float)
    heuristic = metrics["heuristic_nlp_mean_return"].to_numpy(dtype=float)
    ml = metrics["walk_forward_ml_mean_return"].to_numpy(dtype=float)
    baseline_dd = metrics.get("baseline_avg_drawdown")
    heuristic_dd = metrics.get("heuristic_nlp_avg_drawdown")
    ml_dd = metrics.get("walk_forward_ml_avg_drawdown")

    sim_rows: list[dict] = []
    for i in range(iterations):
        idx = rng.integers(0, n_dates, size=n_dates)
        b = float(np.nanmean(baseline[idx]))
        h = float(np.nanmean(heuristic[idx]))
        m = float(np.nanmean(ml[idx]))
        row = {
            "iteration": i,
            "baseline_return": b,
            "heuristic_nlp_return": h,
            "walk_forward_ml_return": m,
            "ml_minus_baseline": m - b,
            "ml_minus_heuristic": m - h,
        }
        if baseline_dd is not None and heuristic_dd is not None and ml_dd is not None:
            bdd = float(np.nanmean(baseline_dd.to_numpy(dtype=float)[idx]))
            hdd = float(np.nanmean(heuristic_dd.to_numpy(dtype=float)[idx]))
            mdd = float(np.nanmean(ml_dd.to_numpy(dtype=float)[idx]))
            row["baseline_drawdown"] = bdd
            row["heuristic_nlp_drawdown"] = hdd
            row["walk_forward_ml_drawdown"] = mdd
            row["ml_drawdown_minus_baseline"] = mdd - bdd
            row["ml_drawdown_minus_heuristic"] = mdd - hdd
        sim_rows.append(row)

    sims = pd.DataFrame(sim_rows)
    lift = sims["ml_minus_baseline"]
    heuristic_lift = sims["ml_minus_heuristic"]
    summary = {
        "test_windows": n_dates,
        "baseline_return": float(np.nanmean(baseline)),
        "heuristic_nlp_return": float(np.nanmean(heuristic)),
        "walk_forward_ml_return": float(np.nanmean(ml)),
        "cash_baseline": cash * float(np.nanmean(baseline)),
        "cash_heuristic_nlp": cash * float(np.nanmean(heuristic)),
        "cash_walk_forward_ml": cash * float(np.nanmean(ml)),
        "cash_ml_minus_baseline": cash * float(np.nanmean(ml) - np.nanmean(baseline)),
        "cash_ml_minus_heuristic": cash * float(np.nanmean(ml) - np.nanmean(heuristic)),
        "prob_ml_beats_baseline": float((lift > 0).mean()),
        "prob_ml_beats_heuristic": float((heuristic_lift > 0).mean()),
        "ml_lift_p05": float(lift.quantile(0.05)),
        "ml_lift_p50": float(lift.quantile(0.50)),
        "ml_lift_p95": float(lift.quantile(0.95)),
        "ml_vs_heuristic_lift_p05": float(heuristic_lift.quantile(0.05)),
        "ml_vs_heuristic_lift_p50": float(heuristic_lift.quantile(0.50)),
        "ml_vs_heuristic_lift_p95": float(heuristic_lift.quantile(0.95)),
    }
    if "ml_drawdown_minus_baseline" in sims.columns:
        summary["prob_ml_drawdown_better_baseline"] = float((sims["ml_drawdown_minus_baseline"] > 0).mean())
        summary["prob_ml_drawdown_better_heuristic"] = float((sims["ml_drawdown_minus_heuristic"] > 0).mean())
    return summary, sims


def main() -> None:
    args = parse_args()
    df = read_table(args.predictions)
    ticker = detect_ticker_column(df, args.ticker_col)
    date = detect_date_column(df, args.date_col)
    if date is None:
        raise SystemExit("Could not detect prediction date column.")
    baseline_col = resolve_confidence_column(df, args.baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline")
    heuristic_col = resolve_confidence_column(df, args.heuristic_confidence_col, HEURISTIC_CONFIDENCE_CANDIDATES, "heuristic")
    ml_col = _resolve_ml_column(df, args.ml_confidence_col)
    rank_cols = {
        "baseline": baseline_col,
        "heuristic_nlp": heuristic_col,
        "walk_forward_ml": ml_col,
    }
    rng = np.random.default_rng(args.seed)

    summaries: list[dict] = []
    all_sims: list[pd.DataFrame] = []
    for return_col in args.return_cols:
        if return_col not in df.columns:
            continue
        for top_n in args.top_ns:
            metrics = per_date_metrics(
                df,
                date_col=date,
                ticker_col=ticker,
                return_col=return_col,
                top_n=int(top_n),
                rank_cols=rank_cols,
            )
            summary, sims = bootstrap_summary(metrics, iterations=args.iterations, rng=rng, cash=args.cash)
            if not summary:
                continue
            summary.update({"return_col": return_col, "top_n": int(top_n), "iterations": int(args.iterations)})
            summaries.append(summary)
            sims["return_col"] = return_col
            sims["top_n"] = int(top_n)
            all_sims.append(sims)

    summary_df = pd.DataFrame(summaries)
    write_table(summary_df, args.out)
    print(f"Saved walk-forward Monte Carlo summary: {args.out}")
    print(f"Rows: {len(summary_df):,}")
    if not summary_df.empty:
        display = [
            "return_col",
            "top_n",
            "cash_ml_minus_baseline",
            "cash_ml_minus_heuristic",
            "prob_ml_beats_baseline",
            "prob_ml_beats_heuristic",
            "prob_ml_drawdown_better_baseline",
        ]
        print(summary_df[[c for c in display if c in summary_df.columns]].to_string(index=False))

    if args.simulations_out:
        simulations = pd.concat(all_sims, ignore_index=True) if all_sims else pd.DataFrame()
        write_table(simulations, args.simulations_out)
        print(f"Saved walk-forward Monte Carlo simulations: {args.simulations_out}")


if __name__ == "__main__":
    main()
