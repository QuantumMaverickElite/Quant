from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unattended multi-source news ML training runner.")
    parser.add_argument("--queries-file", type=Path, default=Path("data/intelligence/historical/sec_eval_tickers.txt"))
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-05-28")
    parser.add_argument("--finnhub-scored", type=Path, default=Path("data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl"))
    parser.add_argument("--massive-out", type=Path, default=Path("data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl"))
    parser.add_argument("--merged-out", type=Path, default=Path("data/intelligence/historical/raw/news_eval_2025_2026_merged_full.jsonl"))
    parser.add_argument("--scored-out", type=Path, default=Path("data/intelligence/historical/raw/news_eval_2025_2026_merged_full_scored.jsonl"))
    parser.add_argument("--work-dir", type=Path, default=Path("outputs/intelligence/training_runs/sec_news_massive_full_pool"))
    parser.add_argument("--massive-offsets", nargs="+", type=int, default=[15, 20, 25, 30, 35, 40, 45])
    parser.add_argument("--chunk-size", type=int, default=5)
    parser.add_argument("--massive-limit", type=int, default=50)
    parser.add_argument("--massive-sleep-seconds", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--backoff-seconds", type=float, default=60.0)
    parser.add_argument("--min-relevance-score", type=float, default=0.25)
    parser.add_argument("--sentiment-backend", choices=["finbert", "heuristic", "auto"], default="finbert")
    parser.add_argument("--sentiment-batch-size", type=int, default=16)
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--train-days-list", nargs="+", type=int, default=[90, 126])
    parser.add_argument("--embargo-days-list", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--alpha-list", nargs="+", default=["3", "10"])
    parser.add_argument("--model-types", nargs="+", default=["logistic"], choices=["logistic", "ridge"])
    parser.add_argument("--min-train-rows-list", nargs="+", type=int, default=[100])
    parser.add_argument("--skip-massive-fetch", action="store_true")
    parser.add_argument("--skip-score", action="store_true")
    parser.add_argument("--force-score", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    return parser.parse_args()


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["step", "returncode", "elapsed_seconds", "command"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_step(name: str, cmd: list[str], *, manifest: Path, rows: list[dict], keep_going: bool) -> None:
    print("\n" + "=" * 80)
    print(name)
    print(" ".join(cmd))
    started = time.time()
    completed = subprocess.run(cmd, text=True)
    elapsed = time.time() - started
    rows.append(
        {
            "step": name,
            "returncode": completed.returncode,
            "elapsed_seconds": round(elapsed, 3),
            "command": " ".join(cmd),
        }
    )
    write_manifest(manifest, rows)
    if completed.returncode != 0 and not keep_going:
        raise SystemExit(completed.returncode)


def main() -> None:
    args = parse_args()
    py = sys.executable
    args.work_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict] = []
    manifest = args.work_dir / "pool_manifest.csv"

    if not args.skip_massive_fetch:
        for offset in args.massive_offsets:
            run_step(
                f"fetch_massive_offset_{offset}",
                [
                    py,
                    "-m",
                    "scripts.fetch_historical_news_sources",
                    "--providers",
                    "massive_news",
                    "--queries-file",
                    str(args.queries_file),
                    "--start",
                    args.start,
                    "--end",
                    args.end,
                    "--limit",
                    str(args.massive_limit),
                    "--query-offset",
                    str(offset),
                    "--max-queries",
                    str(args.chunk_size),
                    "--massive-sleep-seconds",
                    str(args.massive_sleep_seconds),
                    "--max-retries",
                    str(args.max_retries),
                    "--backoff-seconds",
                    str(args.backoff_seconds),
                    "--resume",
                    "--out",
                    str(args.massive_out),
                ],
                manifest=manifest,
                rows=manifest_rows,
                keep_going=args.keep_going,
            )

    run_step(
        "merge_finnhub_massive",
        [
            py,
            "-m",
            "scripts.merge_historical_sources",
            "--inputs",
            str(args.finnhub_scored),
            str(args.massive_out),
            "--out",
            str(args.merged_out),
            "--audit-csv",
            str(args.work_dir / "news_merge_full_audit.csv"),
            "--min-relevance-score",
            str(args.min_relevance_score),
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
    )

    if not args.skip_score:
        if args.scored_out.exists() and not args.force_score:
            print(f"Skipping score step because output exists: {args.scored_out}")
        else:
            run_step(
                "score_merged_news",
                [
                    py,
                    "-m",
                    "scripts.score_historical_news_sentiment",
                    "--input",
                    str(args.merged_out),
                    "--out",
                    str(args.scored_out),
                    "--backend",
                    args.sentiment_backend,
                    "--batch-size",
                    str(args.sentiment_batch_size),
                    "--checkpoint-every",
                    "250",
                    "--nlp-device",
                    args.nlp_device,
                ],
                manifest=manifest,
                rows=manifest_rows,
                keep_going=args.keep_going,
            )

    training_source = args.scored_out if args.scored_out.exists() else args.merged_out
    run_step(
        "train_walk_forward_grid",
        [
            py,
            "-m",
            "scripts.run_intelligence_training_batch",
            "--news-sources",
            str(training_source),
            "--work-dir",
            str(args.work_dir),
            "--iterations",
            str(args.iterations),
            "--train-days-list",
            *[str(v) for v in args.train_days_list],
            "--embargo-days-list",
            *[str(v) for v in args.embargo_days_list],
            "--alpha-list",
            *[str(v) for v in args.alpha_list],
            "--model-types",
            *args.model_types,
            "--min-train-rows-list",
            *[str(v) for v in args.min_train_rows_list],
            "--min-relevance-score",
            str(args.min_relevance_score),
            "--keep-going",
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
    )

    run_step(
        "summarize_training_run",
        [
            py,
            "-m",
            "scripts.summarize_intelligence_training_run",
            "--run-dir",
            str(args.work_dir),
            "--out",
            str(args.work_dir / "all_monte_carlo_ranked.csv"),
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=True,
    )

    print("\nPool training run complete.")
    print(f"Manifest: {manifest}")
    print(f"Summary: {args.work_dir / 'all_monte_carlo_ranked.csv'}")


if __name__ == "__main__":
    main()
