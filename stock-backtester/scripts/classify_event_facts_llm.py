#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os

from backtester.intelligence.llm_event_classifier import classify_event_facts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--events",
        default="outputs/intelligence/event_fact_table.parquet",
        help="Event fact table.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/llm_event_classifications.jsonl",
        help="Output classification table.",
    )
    p.add_argument("--mode", choices=["mock", "api"], default="mock")
    p.add_argument("--max-rows", type=int, default=25)
    p.add_argument("--ticker", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--sleep-seconds", type=float, default=0.0)
    p.add_argument("--text-limit", type=int, default=1800)
    p.add_argument("--no-response-format", action="store_true")
    args = p.parse_args()

    df = classify_event_facts(
        events_path=args.events,
        out_path=args.out,
        mode=args.mode,
        max_rows=args.max_rows,
        ticker=args.ticker,
        force=args.force,
        sleep_seconds=args.sleep_seconds,
        text_limit=args.text_limit,
        use_response_format=not args.no_response_format,
    )

    print(f"mode: {args.mode}")
    print(f"rows classified this run: {len(df)}")
    print(f"wrote: {args.out}")

    if args.mode == "api":
        print(f"api base env set: {bool(os.environ.get('OPENAI_COMPAT_API_BASE'))}")
        print(f"model env set: {bool(os.environ.get('OPENAI_COMPAT_MODEL'))}")


if __name__ == "__main__":
    main()
