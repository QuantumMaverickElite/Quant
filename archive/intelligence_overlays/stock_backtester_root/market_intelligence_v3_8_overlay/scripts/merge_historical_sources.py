from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_source_merge import merge_historical_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge and dedupe historical intelligence/news source JSONL files.")
    parser.add_argument("--inputs", nargs="+", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--min-published-at")
    parser.add_argument("--max-published-at")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, stats = merge_historical_sources(
        inputs=args.inputs,
        out_path=args.out,
        min_published_at=args.min_published_at,
        max_published_at=args.max_published_at,
    )
    print(f"Saved merged historical sources: {args.out}")
    for key, value in stats.items():
        print(f"{key}: {value:,}")


if __name__ == "__main__":
    main()
