from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_monte_carlo import run_allocator_monte_carlo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monte Carlo robustness test for allocator intelligence.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--return-col", default="next_10d_return")
    parser.add_argument("--drawdown-col")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--include-duplicate-rows", action="store_true")
    parser.add_argument("--summary-out", type=Path, default=Path("outputs/intelligence/allocator_monte_carlo_summary.csv"))
    parser.add_argument("--simulations-out", type=Path, default=Path("outputs/intelligence/allocator_monte_carlo_simulations.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_allocator_monte_carlo(
        signals_path=args.signals,
        return_col=args.return_col,
        top_n=args.top_n,
        iterations=args.iterations,
        seed=args.seed,
        drawdown_col=args.drawdown_col,
        unique_tickers=not args.include_duplicate_rows,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.simulations_out.parent.mkdir(parents=True, exist_ok=True)
    result.summary.to_csv(args.summary_out, index=False)
    result.simulations.to_csv(args.simulations_out, index=False)

    print("Allocator Intelligence Monte Carlo")
    print(f"Return column: {args.return_col}")
    print(f"Top N: {args.top_n}")
    print(f"Iterations: {args.iterations}")
    print(result.summary.to_string(index=False))
    print(f"Saved summary: {args.summary_out}")
    print(f"Saved simulations: {args.simulations_out}")


if __name__ == "__main__":
    main()
