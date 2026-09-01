from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.sec_source_collector import (
    DEFAULT_FORMS,
    fetch_sec_historical_sources,
    parse_ymd,
    write_sec_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch SEC EDGAR point-in-time filing sources.")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--forms", nargs="+", default=list(DEFAULT_FORMS))
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT"))
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument("--skip-older-files", action="store_true")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/intelligence/historical/raw/sec_sources.jsonl"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.user_agent:
        raise SystemExit(
            "Provide --user-agent or SEC_USER_AGENT. "
            "Use a descriptive value such as 'stock-backtester elijah@example.com'."
        )

    records = fetch_sec_historical_sources(
        tickers=args.tickers,
        start=parse_ymd(args.start),
        end=parse_ymd(args.end),
        forms=tuple(args.forms),
        user_agent=args.user_agent,
        include_older_files=not args.skip_older_files,
        sleep_seconds=args.sleep_seconds,
    )
    write_sec_records(records, args.out)

    print("Provider: sec_edgar")
    print(f"Tickers: {', '.join(t.upper() for t in args.tickers)}")
    print(f"Date range: {args.start} to {args.end}")
    print(f"Forms: {', '.join(args.forms)}")
    print(f"Records: {len(records)}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
