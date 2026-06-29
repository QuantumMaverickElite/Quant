from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_news_sentiment import enrich_historical_news_sentiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score historical news JSONL sentiment with FinBERT or heuristic backend.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--backend", choices=["finbert", "heuristic", "auto"], default="finbert")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--include-analyst", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=250)
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = enrich_historical_news_sentiment(
        input_jsonl=args.input,
        output_jsonl=args.out,
        backend=args.backend,
        batch_size=args.batch_size,
        limit=args.limit,
        include_analyst=args.include_analyst,
        checkpoint_every=args.checkpoint_every,
        nlp_device=args.nlp_device,
    )
    scored = 0
    for row in rows:
        raw = row.get("raw")
        if isinstance(raw, dict) and raw.get("model_sentiment_score") is not None:
            scored += 1
    print(f"Saved sentiment-enriched historical news: {args.out}")
    print(f"Rows: {len(rows):,}")
    print(f"Rows with model sentiment: {scored:,}")


if __name__ == "__main__":
    main()
