from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_diagnostics import compare_topn_grid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare pre/post intelligence allocator rankings.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 50])
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--include-duplicate-rows", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("outputs/intelligence/allocator_intelligence_comparison.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = compare_topn_grid(
        signals_path=args.signals,
        top_ns=args.top_ns,
        return_cols=args.return_cols,
        unique_tickers=not args.include_duplicate_rows,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    print("Allocator Intelligence Comparison")
    print(f"Rows: {len(out)}")
    if len(out):
        display_cols = [
            col
            for col in [
                "return_col",
                "top_n",
                "unique_tickers",
                "pre_return",
                "post_return",
                "post_minus_pre",
                "pre_hit_rate",
                "post_hit_rate",
                "pre_avg_drawdown",
                "post_avg_drawdown",
                "drawdown_delta",
                "overlap_count",
                "entered_count",
                "dropped_count",
            ]
            if col in out.columns
        ]
        print(out[display_cols].to_string(index=False))
    print(f"Saved comparison: {args.out}")


if __name__ == "__main__":
    main()
