from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path


def parse_period(value: str) -> tuple[str, str, str]:
    if "=" not in value or ":" not in value:
        raise argparse.ArgumentTypeError("Period must be label=start:end, e.g. 2022_2023=2022-01-01:2023-12-31")
    label, bounds = value.split("=", 1)
    start, end = bounds.split(":", 1)
    return label.strip(), start.strip(), end.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run expanded multi-period intelligence ML research jobs.")
    parser.add_argument(
        "--periods",
        nargs="+",
        type=parse_period,
        default=[
            ("2020_2021", "2020-01-01", "2021-12-31"),
            ("2022_2023", "2022-01-01", "2023-12-31"),
            ("2024_2026", "2024-01-01", "2026-05-28"),
        ],
    )
    parser.add_argument("--signals", type=Path, default=Path("outputs/signals/mean_reversion_latest_with_intelligence.parquet"))
    parser.add_argument("--work-root", type=Path, default=Path("outputs/intelligence/training_runs/multi_period_ml_research"))
    parser.add_argument("--download-prices", action="store_true")
    parser.add_argument("--fetch-news", action="store_true")
    parser.add_argument("--include-massive", action="store_true")
    parser.add_argument("--include-newsapi", action="store_true")
    parser.add_argument("--include-polygon", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--chunk-size", type=int, default=5)
    parser.add_argument("--massive-sleep-seconds", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--backoff-seconds", type=float, default=60.0)
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--equity-iterations", type=int, default=10_000)
    parser.add_argument("--train-days-list", nargs="+", type=int, default=[126, 252])
    parser.add_argument("--embargo-days-list", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--alpha-list", nargs="+", default=["3", "10", "30"])
    parser.add_argument("--model-types", nargs="+", choices=["logistic", "ridge"], default=["logistic"])
    parser.add_argument("--min-train-rows-list", nargs="+", type=int, default=[100, 200])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["period", "returncode", "elapsed_seconds", "command"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_period(label: str, start: str, end: str, args: argparse.Namespace, manifest_rows: list[dict]) -> None:
    py = sys.executable
    work_dir = args.work_root / label
    cmd = [
        py,
        "-m",
        "scripts.run_historical_intelligence_stress",
        "--signals",
        str(args.signals),
        "--start",
        start,
        "--end",
        end,
        "--work-dir",
        str(work_dir),
        "--score-sentiment",
        "--nlp-device",
        args.nlp_device,
        "--iterations",
        str(args.iterations),
        "--equity-iterations",
        str(args.equity_iterations),
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
        "--top-ns",
        *[str(v) for v in args.top_ns],
        "--return-cols",
        *args.return_cols,
        "--keep-going",
    ]
    if args.download_prices:
        cmd.append("--download-prices")
    if args.fetch_news:
        cmd.append("--fetch-news")
    if args.include_massive:
        cmd.append("--include-massive")
    if args.include_newsapi:
        cmd.append("--include-newsapi")
    if args.include_polygon:
        cmd.append("--include-polygon")
    if args.skip_existing:
        cmd.append("--skip-existing")
    cmd.extend(
        [
            "--limit",
            str(args.limit),
            "--chunk-size",
            str(args.chunk_size),
            "--massive-sleep-seconds",
            str(args.massive_sleep_seconds),
            "--max-retries",
            str(args.max_retries),
            "--backoff-seconds",
            str(args.backoff_seconds),
        ]
    )

    print("\n" + "=" * 88)
    print(f"Period {label}: {start}..{end}")
    print(" ".join(cmd))
    started = time.time()
    if args.dry_run:
        returncode = 0
    else:
        completed = subprocess.run(cmd, text=True)
        returncode = completed.returncode
    elapsed = time.time() - started
    manifest_rows.append(
        {
            "period": label,
            "returncode": returncode,
            "elapsed_seconds": round(elapsed, 3),
            "command": " ".join(cmd),
        }
    )
    write_manifest(args.work_root / "multi_period_manifest.csv", manifest_rows)
    if returncode != 0 and not args.keep_going:
        raise SystemExit(returncode)


def main() -> None:
    args = parse_args()
    args.work_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict] = []
    for label, start, end in args.periods:
        run_period(label, start, end, args, manifest_rows)
    print("\nMulti-period research run complete.")
    print(f"Manifest: {args.work_root / 'multi_period_manifest.csv'}")


if __name__ == "__main__":
    main()
