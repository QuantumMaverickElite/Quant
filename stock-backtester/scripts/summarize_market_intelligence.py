from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.brief import build_market_intelligence_brief, read_signals, write_brief


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a readable market intelligence brief.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("outputs/intelligence/latest_market_intelligence_brief.txt"))
    parser.add_argument("--summary-csv", type=Path, default=Path("outputs/intelligence/latest_market_intelligence_summary.csv"))
    parser.add_argument("--top-n", type=int, default=15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    signals = read_signals(args.signals)
    text, summary = build_market_intelligence_brief(signals, top_n=args.top_n)
    write_brief(text, args.out)
    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_csv, index=False)
    print(text)
    print("")
    print(f"Saved brief: {args.out}")
    print(f"Saved summary: {args.summary_csv}")


if __name__ == "__main__":
    main()
