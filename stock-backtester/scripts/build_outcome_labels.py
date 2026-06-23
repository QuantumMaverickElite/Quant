from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.outcome_labels import build_outcome_labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build forward outcome labels for signal calibration.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--download-prices", action="store_true")
    parser.add_argument("--download-period", default="10y")
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--horizons", nargs="+", type=int, default=[5, 20])
    parser.add_argument("--success-horizon", type=int, default=20)
    parser.add_argument("--success-return-threshold", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = build_outcome_labels(
        signals_path=args.signals,
        prices_path=args.prices,
        out_path=args.out,
        ticker_col=args.ticker_col,
        date_col=args.date_col,
        horizons=tuple(args.horizons),
        success_horizon=args.success_horizon,
        success_return_threshold=args.success_return_threshold,
        download_prices_flag=args.download_prices,
        download_period=args.download_period,
    )
    print(f"Saved outcome-labeled signals: {args.out}")
    print(f"Rows: {len(out):,}")


if __name__ == "__main__":
    main()
