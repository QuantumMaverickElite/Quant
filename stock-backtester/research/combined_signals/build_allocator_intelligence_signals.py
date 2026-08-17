from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_adjustment import build_allocator_ready_signals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create allocator-ready signals with intelligence-adjusted confidence.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--confidence-col", default="adjusted_confidence")
    parser.add_argument("--include-historical", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = build_allocator_ready_signals(
        signals_path=args.signals,
        out_path=args.out,
        confidence_col=args.confidence_col,
        latest_date_only=not args.include_historical,
    )
    print(f"Saved allocator-ready intelligence signals: {args.out}")
    print(f"Rows: {len(out):,}")
    if "intelligence_action_label" in out.columns:
        print(out["intelligence_action_label"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
