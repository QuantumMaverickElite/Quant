from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_panel_builder import build_historical_panel_seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a historical signal seed panel for walk-forward intelligence training.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--rank-col")
    parser.add_argument("--tickers-file", type=Path)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--top-n-per-date", type=int, default=50)
    parser.add_argument("--min-rank-value", type=float)
    parser.add_argument("--max-dates", type=int)
    parser.add_argument("--exclude-latest-date", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = build_historical_panel_seed(
        signals_path=args.signals,
        out_path=args.out,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
        rank_col=args.rank_col,
        tickers_file=args.tickers_file,
        start=args.start,
        end=args.end,
        top_n_per_date=args.top_n_per_date,
        min_rank_value=args.min_rank_value,
        max_dates=args.max_dates,
        exclude_latest_date=args.exclude_latest_date,
    )
    print(f"Saved historical panel seed: {args.out}")
    print(f"Rows: {len(out):,}")
    print(f"Columns: {len(out.columns):,}")
    print(out.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
