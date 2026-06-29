#!/usr/bin/env python3
"""Lightweight intraday news polling loop with bounded cache ingestion.

This wraps the existing `scripts.fetch_historical_news_sources` command and then ingests
new JSONL records into `live_intelligence_cache.py`. It intentionally does not retrain a
large model continuously. It collects/scans current-day evidence for inference now and
later labeling/retraining.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path


def run_cmd(cmd: list[str], dry_run: bool = False) -> int:
    print("$ " + " ".join(shlex.quote(x) for x in cmd), flush=True)
    if dry_run:
        return 0
    return subprocess.call(cmd)


def trim_queries_file(src: Path, dst: Path, max_tickers: int) -> int:
    tickers: list[str] = []
    with src.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip().upper().lstrip("$")
            if not s or s.startswith("#"):
                continue
            if s not in tickers:
                tickers.append(s)
            if len(tickers) >= max_tickers:
                break
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(tickers) + "\n", encoding="utf-8")
    return len(tickers)


def one_poll(args: argparse.Namespace, iteration: int) -> int:
    today = date.today().isoformat()
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    queries_file = Path(args.queries_file)
    bounded_queries = work_dir / f"live_queries_top{args.max_tickers}.txt"
    n = trim_queries_file(queries_file, bounded_queries, args.max_tickers)
    if n == 0:
        print(f"No tickers found in {queries_file}")
        return 2

    out_jsonl = work_dir / f"live_news_{today}_{stamp}.jsonl"
    providers = args.providers.split(",") if isinstance(args.providers, str) else args.providers

    fetch_cmd = [
        sys.executable,
        "-m",
        "scripts.fetch_historical_news_sources",
        "--providers",
        *providers,
        "--queries-file",
        str(bounded_queries),
        "--start",
        today,
        "--end",
        today,
        "--limit",
        str(args.limit),
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--max-retries",
        str(args.max_retries),
        "--backoff-seconds",
        str(args.backoff_seconds),
        "--resume",
        "--mark-empty-complete",
        "--out",
        str(out_jsonl),
    ]
    if args.max_http_requests is not None:
        fetch_cmd.extend(["--max-http-requests", str(args.max_http_requests)])

    rc = run_cmd(fetch_cmd, args.dry_run)
    if rc != 0:
        print(f"fetch failed rc={rc}")
        return rc

    if not args.dry_run and out_jsonl.exists() and out_jsonl.stat().st_size > 0:
        ingest_cmd = [
            sys.executable,
            "scripts/live_intelligence_cache.py",
            "ingest-jsonl",
            "--db",
            args.cache_db,
            "--jsonl",
            str(out_jsonl),
            "--raw-ttl-days",
            str(args.raw_ttl_days),
        ]
        if args.keep_raw:
            ingest_cmd.append("--keep-raw")
        if args.keep_raw_official:
            ingest_cmd.append("--keep-raw-official")
        rc = run_cmd(ingest_cmd, args.dry_run)
        if rc != 0:
            return rc

        expire_cmd = [
            sys.executable,
            "scripts/live_intelligence_cache.py",
            "expire",
            "--db",
            args.cache_db,
            "--raw-ttl-days",
            str(args.raw_ttl_days),
            "--feature-retention-days",
            str(args.feature_retention_days),
            "--max-mb",
            str(args.cache_max_mb),
        ]
        rc = run_cmd(expire_cmd, args.dry_run)
        if rc != 0:
            return rc

    if args.inference_command:
        # Optional hook. The command receives environment vars rather than a complex schema.
        env = os.environ.copy()
        env.update({
            "LIVE_INTEL_CACHE_DB": args.cache_db,
            "LIVE_INTEL_JSONL": str(out_jsonl),
            "LIVE_INTEL_QUERIES_FILE": str(bounded_queries),
        })
        print("$ " + args.inference_command, flush=True)
        if not args.dry_run:
            rc = subprocess.call(args.inference_command, shell=True, env=env)
            if rc != 0:
                return rc

    if args.delete_raw_jsonl_after_ingest and not args.keep_raw and out_jsonl.exists() and not args.dry_run:
        out_jsonl.unlink()
        print(f"deleted transient JSONL {out_jsonl}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries-file", required=True, help="Ticker file. Only first --max-tickers are polled.")
    ap.add_argument("--providers", default="finnhub_news,rss_yahoo,rss_google", help="Comma-separated providers for existing fetcher")
    ap.add_argument("--work-dir", default="outputs/intelligence/live_intraday", help="Transient live workspace")
    ap.add_argument("--cache-db", default="data/intelligence/cache/live_intelligence.sqlite")
    ap.add_argument("--max-tickers", type=int, default=150)
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--sleep-seconds", type=float, default=0.5)
    ap.add_argument("--max-retries", type=int, default=3, help="Keep live retries bounded. Resume can retry later.")
    ap.add_argument("--backoff-seconds", type=float, default=30.0)
    ap.add_argument("--max-http-requests", type=int)
    ap.add_argument("--poll-seconds", type=int, default=600)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--raw-ttl-days", type=int, default=14)
    ap.add_argument("--feature-retention-days", type=int, default=730)
    ap.add_argument("--cache-max-mb", type=float, default=2048.0)
    ap.add_argument("--keep-raw", action="store_true", help="Store compressed raw JSON in cache until TTL. Default only stores compact metadata.")
    ap.add_argument("--keep-raw-official", action="store_true")
    ap.add_argument("--delete-raw-jsonl-after-ingest", action="store_true", help="Remove transient provider JSONL after ingest")
    ap.add_argument("--inference-command", help="Optional shell command run after each poll. Receives LIVE_INTEL_* env vars.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    iteration = 0
    while True:
        iteration += 1
        print(f"\n=== live intraday poll {iteration} at {datetime.now().isoformat(timespec='seconds')} ===", flush=True)
        rc = one_poll(args, iteration)
        if args.once:
            return rc
        sleep_for = max(60, args.poll_seconds)
        print(f"sleeping {sleep_for}s", flush=True)
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
