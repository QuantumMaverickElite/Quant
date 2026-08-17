from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_monte_carlo import run_allocator_monte_carlo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Monte Carlo grid comparing the baseline volatility/entropy/"
            "correlation/mean-reversion ranking against the NLP-adjusted ranking."
        )
    )
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--include-duplicate-rows", action="store_true")
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("outputs/intelligence/strategy_nlp_monte_carlo_grid.csv"),
    )
    parser.add_argument(
        "--raw-summary-out",
        type=Path,
        default=Path("outputs/intelligence/strategy_nlp_monte_carlo_raw_summary.csv"),
    )
    return parser.parse_args()


def metric_value(summary: pd.DataFrame, metric: str) -> float:
    rows = summary[summary["metric"].eq(metric)]
    if rows.empty:
        return float("nan")
    return float(rows["value"].iloc[0])


def compact_row(*, return_col: str, top_n: int, summary: pd.DataFrame) -> dict:
    pre_return = metric_value(summary, "deterministic_pre_return")
    post_return = metric_value(summary, "deterministic_post_return")
    pre_drawdown = metric_value(summary, "deterministic_pre_avg_drawdown")
    post_drawdown = metric_value(summary, "deterministic_post_avg_drawdown")
    return {
        "return_col": return_col,
        "top_n": top_n,
        "baseline_return": pre_return,
        "nlp_adjusted_return": post_return,
        "nlp_minus_baseline": metric_value(summary, "deterministic_post_minus_pre"),
        "baseline_avg_drawdown": pre_drawdown,
        "nlp_avg_drawdown": post_drawdown,
        "drawdown_delta": metric_value(summary, "deterministic_drawdown_delta"),
        "prob_nlp_beats_baseline": metric_value(summary, "bootstrap_prob_post_beats_pre"),
        "lift_p05": metric_value(summary, "bootstrap_lift_p05"),
        "lift_p50": metric_value(summary, "bootstrap_lift_p50"),
        "lift_p95": metric_value(summary, "bootstrap_lift_p95"),
        "prob_baseline_beats_random": metric_value(summary, "random_prob_pre_beats_random"),
        "prob_nlp_beats_random": metric_value(summary, "random_prob_post_beats_random"),
        "prob_nlp_drawdown_better": metric_value(summary, "bootstrap_prob_post_drawdown_better"),
    }


def main() -> None:
    args = parse_args()
    compact_rows: list[dict] = []
    raw_summaries: list[pd.DataFrame] = []

    for return_col in args.return_cols:
        for top_n in args.top_ns:
            result = run_allocator_monte_carlo(
                signals_path=args.signals,
                return_col=return_col,
                top_n=top_n,
                iterations=args.iterations,
                seed=args.seed + top_n + abs(hash(return_col)) % 10000,
                unique_tickers=not args.include_duplicate_rows,
            )
            summary = result.summary.copy()
            summary.insert(0, "return_col", return_col)
            raw_summaries.append(summary)
            compact_rows.append(compact_row(return_col=return_col, top_n=top_n, summary=result.summary))

    compact = pd.DataFrame(compact_rows)
    raw = pd.concat(raw_summaries, ignore_index=True, sort=False) if raw_summaries else pd.DataFrame()

    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_summary_out.parent.mkdir(parents=True, exist_ok=True)
    compact.to_csv(args.summary_out, index=False)
    raw.to_csv(args.raw_summary_out, index=False)

    print("Strategy NLP Monte Carlo Grid")
    print(f"Signals: {args.signals}")
    print(f"Iterations per test: {args.iterations}")
    print(f"Tests: {len(compact)}")
    if len(compact):
        display_cols = [
            "return_col",
            "top_n",
            "baseline_return",
            "nlp_adjusted_return",
            "nlp_minus_baseline",
            "drawdown_delta",
            "prob_nlp_beats_baseline",
            "prob_nlp_beats_random",
            "prob_nlp_drawdown_better",
        ]
        print(compact[display_cols].to_string(index=False))
    print(f"Saved grid summary: {args.summary_out}")
    print(f"Saved raw summary: {args.raw_summary_out}")


if __name__ == "__main__":
    main()
