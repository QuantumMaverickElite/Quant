from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.opportunity_scorer import add_opportunity_scores_to_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add balanced risk/opportunity event scores to intelligence features.")
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-boost", type=float, default=0.25)
    parser.add_argument("--max-event-penalty", type=float, default=0.45)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = add_opportunity_scores_to_csv(
        in_csv=args.features,
        out_csv=args.out,
        max_boost=args.max_boost,
        max_event_penalty=args.max_event_penalty,
    )
    print(f"Saved opportunity-scored features: {args.out}")
    print(f"Rows: {len(out)}")
    cols = [
        col
        for col in [
            "query",
            "event_opportunity_score",
            "event_downside_risk_score",
            "event_opportunity_multiplier",
            "event_downside_multiplier",
            "net_event_multiplier",
            "net_event_score",
        ]
        if col in out.columns
    ]
    print(out[cols].sort_values("net_event_score", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
