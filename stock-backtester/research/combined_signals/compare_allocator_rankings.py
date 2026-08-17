from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_diagnostics import dedupe_by_ticker, evaluated_rows
from backtester.intelligence.candidates import read_table


DEFAULT_RANKINGS = {
    "baseline": "allocator_confidence_pre_intelligence",
    "heuristic_nlp": "allocator_confidence_intelligence_adjusted",
    "ml_nlp": "allocator_confidence_ml_intelligence_adjusted",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare arbitrary allocator ranking columns.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--cash", type=float, default=10000.0)
    parser.add_argument("--include-duplicate-rows", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("outputs/intelligence/allocator_ranking_comparison.csv"))
    return parser.parse_args()


def drawdown_col_for(return_col: str) -> str:
    if return_col.startswith("next_") and return_col.endswith("_return"):
        return f"max_drawdown_{return_col.removesuffix('_return')}"
    return return_col.replace("next_", "max_drawdown_next_")


def select_top(df: pd.DataFrame, score_col: str, top_n: int, unique_tickers: bool) -> pd.DataFrame:
    clean = df.dropna(subset=[score_col]).copy()
    if unique_tickers:
        clean = dedupe_by_ticker(clean, score_col=score_col)
    return clean.sort_values(score_col, ascending=False).head(top_n)


def main() -> None:
    args = parse_args()
    df = evaluated_rows(read_table(args.signals))
    rankings = {name: col for name, col in DEFAULT_RANKINGS.items() if col in df.columns}
    if len(rankings) < 2:
        raise SystemExit("Need at least two ranking columns to compare.")

    rows: list[dict] = []
    for return_col in args.return_cols:
        if return_col not in df.columns:
            continue
        drawdown_col = drawdown_col_for(return_col)
        valid = df.dropna(subset=[return_col]).copy()
        for top_n in args.top_ns:
            selected = {
                name: select_top(valid, col, top_n, unique_tickers=not args.include_duplicate_rows)
                for name, col in rankings.items()
            }
            baseline = selected.get("baseline")
            baseline_return = float(baseline[return_col].mean()) if baseline is not None and len(baseline) else float("nan")
            baseline_tickers = set(baseline["ticker"].astype(str)) if baseline is not None and "ticker" in baseline else set()
            for name, basket in selected.items():
                tickers = set(basket["ticker"].astype(str)) if "ticker" in basket else set()
                row = {
                    "return_col": return_col,
                    "top_n": top_n,
                    "ranking": name,
                    "score_col": rankings[name],
                    "mean_return": float(basket[return_col].mean()) if len(basket) else float("nan"),
                    "hit_rate": float(basket[return_col].gt(0).mean()) if len(basket) else float("nan"),
                    "cash_pnl": float(args.cash * basket[return_col].mean()) if len(basket) else float("nan"),
                    "vs_baseline_return": float(basket[return_col].mean() - baseline_return) if len(basket) else float("nan"),
                    "vs_baseline_cash": float(args.cash * (basket[return_col].mean() - baseline_return)) if len(basket) else float("nan"),
                    "overlap_with_baseline": len(tickers & baseline_tickers),
                    "entered_vs_baseline": len(tickers - baseline_tickers),
                    "dropped_vs_baseline": len(baseline_tickers - tickers),
                }
                if drawdown_col in basket.columns:
                    row["avg_drawdown"] = float(basket[drawdown_col].mean())
                    row["cash_avg_drawdown"] = float(args.cash * basket[drawdown_col].mean())
                rows.append(row)

    out = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print("Allocator Ranking Comparison")
    print(f"Signals: {args.signals}")
    print(f"Rankings: {', '.join(rankings)}")
    print(f"Rows: {len(out)}")
    if len(out):
        display_cols = [
            "return_col",
            "top_n",
            "ranking",
            "mean_return",
            "cash_pnl",
            "vs_baseline_cash",
            "hit_rate",
            "avg_drawdown",
            "cash_avg_drawdown",
            "overlap_with_baseline",
        ]
        display_cols = [col for col in display_cols if col in out.columns]
        print(out[display_cols].to_string(index=False))
    print(f"Saved comparison: {args.out}")


if __name__ == "__main__":
    main()
