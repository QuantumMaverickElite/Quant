from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.candidates import write_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize a historical intelligence training run.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--top", type=int, default=40)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = sorted(args.run_dir.glob("*_monte_carlo.csv"))
    if not files:
        raise SystemExit(f"No *_monte_carlo.csv files found in {args.run_dir}")

    frames: list[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path)
        df["config"] = path.name.replace("_monte_carlo.csv", "")
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    sort_cols = [col for col in ["cash_ml_minus_baseline", "prob_ml_beats_baseline", "cash_ml_minus_heuristic"] if col in out.columns]
    out = out.sort_values(sort_cols, ascending=False) if sort_cols else out

    if args.out:
        write_table(out, args.out)
        print(f"Saved training run summary: {args.out}")
    display = [
        "config",
        "return_col",
        "top_n",
        "cash_ml_minus_baseline",
        "cash_ml_minus_heuristic",
        "prob_ml_beats_baseline",
        "prob_ml_beats_heuristic",
        "prob_ml_drawdown_better_baseline",
        "test_windows",
    ]
    print(out[[c for c in display if c in out.columns]].head(args.top).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
