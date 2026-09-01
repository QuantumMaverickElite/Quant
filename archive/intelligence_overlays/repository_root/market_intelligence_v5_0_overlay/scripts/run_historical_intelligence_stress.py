from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a point-in-time historical stress test for baseline vs NLP/ML allocator rankings."
    )
    parser.add_argument("--signals", type=Path, default=Path("outputs/signals/mean_reversion_latest_with_intelligence.parquet"))
    parser.add_argument("--work-dir", type=Path, default=Path("outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment"))
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2023-12-31")
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--rank-col")
    parser.add_argument("--top-n-per-date", type=int, default=50)
    parser.add_argument("--min-rank-value", type=float)
    parser.add_argument("--max-dates", type=int)
    parser.add_argument("--download-prices", action="store_true")
    parser.add_argument("--download-period", default="10y")
    parser.add_argument("--horizons", nargs="+", type=int, default=[5, 10, 20])
    parser.add_argument("--success-horizon", type=int, default=10)
    parser.add_argument("--queries-file", type=Path)
    parser.add_argument("--fetch-sec", action="store_true")
    parser.add_argument("--sec-sources", nargs="*", type=Path, default=[])
    parser.add_argument("--sec-user-agent", default=os.environ.get("SEC_USER_AGENT"))
    parser.add_argument("--sec-forms", nargs="+", default=["10-K", "10-Q", "8-K", "S-1", "424B", "DEF"])
    parser.add_argument("--sec-sleep-seconds", type=float, default=0.25)
    parser.add_argument("--fetch-news", action="store_true")
    parser.add_argument("--news-sources", nargs="*", type=Path, default=[])
    parser.add_argument("--fetch-providers", nargs="+", default=["finnhub_news", "finnhub_recommendations"])
    parser.add_argument("--include-massive", action="store_true")
    parser.add_argument("--include-newsapi", action="store_true")
    parser.add_argument("--include-polygon", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--chunk-size", type=int, default=5)
    parser.add_argument("--query-offsets", nargs="+", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--massive-sleep-seconds", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--backoff-seconds", type=float, default=60.0)
    parser.add_argument("--min-relevance-score", type=float, default=0.25)
    parser.add_argument("--score-sentiment", action="store_true")
    parser.add_argument("--sentiment-backend", choices=["finbert", "heuristic", "auto"], default="finbert")
    parser.add_argument("--sentiment-batch-size", type=int, default=16)
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument("--equity-iterations", type=int, default=25_000)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--equity-return-col", default="next_5d_return")
    parser.add_argument("--equity-top-n", type=int, default=5)
    parser.add_argument("--windows", nargs="+", type=int, default=[1, 7, 30, 90])
    parser.add_argument("--train-days-list", nargs="+", type=int, default=[126, 252])
    parser.add_argument("--embargo-days-list", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--alpha-list", nargs="+", default=["3", "10", "30"])
    parser.add_argument("--model-types", nargs="+", choices=["logistic", "ridge"], default=["logistic"])
    parser.add_argument("--min-train-rows-list", nargs="+", type=int, default=[100, 200])
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--min-test-rows", type=int, default=5)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    return parser.parse_args()


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["step", "returncode", "elapsed_seconds", "command"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_step(
    name: str,
    cmd: list[str],
    *,
    manifest: Path,
    rows: list[dict],
    keep_going: bool,
    skip_if_exists: Path | None = None,
) -> None:
    if skip_if_exists is not None and skip_if_exists.exists():
        print(f"\n{name}: skipped existing {skip_if_exists}")
        rows.append({"step": name, "returncode": 0, "elapsed_seconds": 0.0, "command": "SKIPPED"})
        write_manifest(manifest, rows)
        return

    print("\n" + "=" * 88)
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


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path}")


def detect_column(df: pd.DataFrame, requested: str | None, candidates: tuple[str, ...], label: str) -> str:
    if requested:
        if requested not in df.columns:
            raise SystemExit(f"{label} column not found: {requested}")
        return requested
    lower = {str(col).lower(): str(col) for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    raise SystemExit(f"Could not detect {label} column. Tried: {', '.join(candidates)}")


def validate_signal_coverage(args: argparse.Namespace) -> None:
    if not args.signals.exists():
        raise SystemExit(f"Signal file not found: {args.signals}")
    df = read_table(args.signals)
    date_col = detect_column(df, args.date_col, ("date", "signal_date", "as_of", "timestamp"), "date")
    dates = pd.to_datetime(df[date_col], errors="coerce")
    mask = dates.ge(pd.Timestamp(args.start)) & dates.le(pd.Timestamp(args.end))
    rows = int(mask.sum())
    unique_dates = int(dates[mask].nunique())
    print(f"Base signal coverage {args.start}..{args.end}: rows={rows:,}, dates={unique_dates:,}")
    if rows == 0 or unique_dates < 20:
        raise SystemExit(
            "Insufficient 2022-2023 base strategy signal coverage. Rebuild the existing allocator signals "
            "for this date range first, then rerun this stress test."
        )


def write_queries_from_seed(seed_path: Path, queries_path: Path, ticker_col: str | None) -> None:
    df = read_table(seed_path)
    ticker = detect_column(df, ticker_col, ("ticker", "query", "symbol"), "ticker")
    tickers = sorted({str(value).upper().strip() for value in df[ticker].dropna() if str(value).strip()})
    queries_path.parent.mkdir(parents=True, exist_ok=True)
    queries_path.write_text("\n".join(tickers) + "\n", encoding="utf-8")
    print(f"Saved stress-test tickers: {queries_path} ({len(tickers)} tickers)")


def count_queries(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def read_queries(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.strip().upper() for line in f if line.strip()]


def write_combined_jsonl(inputs: list[Path], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as dst:
        for path in inputs:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as src:
                for line in src:
                    if line.strip():
                        dst.write(line if line.endswith("\n") else line + "\n")
    return out


def provider_list(args: argparse.Namespace) -> list[str]:
    providers = list(args.fetch_providers)
    if args.include_newsapi and "newsapi" not in providers:
        providers.append("newsapi")
    if args.include_polygon and "polygon_news" not in providers:
        providers.append("polygon_news")
    return providers


def fetch_chunks(
    args: argparse.Namespace,
    *,
    py: str,
    queries_file: Path,
    manifest: Path,
    manifest_rows: list[dict],
) -> list[Path]:
    fetched: list[Path] = []
    total_queries = count_queries(queries_file)
    offsets = args.query_offsets or list(range(0, total_queries, args.chunk_size))
    base_providers = provider_list(args)

    if base_providers:
        out = args.work_dir / f"news_{args.start}_{args.end}_providers.jsonl"
        for offset in offsets:
            run_step(
                f"fetch_news_offset_{offset}",
                [
                    py,
                    "-m",
                    "scripts.fetch_historical_news_sources",
                    "--providers",
                    *base_providers,
                    "--queries-file",
                    str(queries_file),
                    "--start",
                    args.start,
                    "--end",
                    args.end,
                    "--limit",
                    str(args.limit),
                    "--sleep-seconds",
                    str(args.sleep_seconds),
                    "--query-offset",
                    str(offset),
                    "--max-queries",
                    str(args.chunk_size),
                    "--max-retries",
                    str(args.max_retries),
                    "--backoff-seconds",
                    str(args.backoff_seconds),
                    "--resume",
                    "--mark-empty-complete",
                    "--out",
                    str(out),
                ],
                manifest=manifest,
                rows=manifest_rows,
                keep_going=args.keep_going,
            )
        fetched.append(out)

    if args.include_massive:
        out = args.work_dir / f"news_{args.start}_{args.end}_massive.jsonl"
        for offset in offsets:
            run_step(
                f"fetch_massive_offset_{offset}",
                [
                    py,
                    "-m",
                    "scripts.fetch_historical_news_sources",
                    "--providers",
                    "massive_news",
                    "--queries-file",
                    str(queries_file),
                    "--start",
                    args.start,
                    "--end",
                    args.end,
                    "--limit",
                    str(min(args.limit, 50)),
                    "--sleep-seconds",
                    str(args.sleep_seconds),
                    "--massive-sleep-seconds",
                    str(args.massive_sleep_seconds),
                    "--query-offset",
                    str(offset),
                    "--max-queries",
                    str(args.chunk_size),
                    "--max-retries",
                    str(args.max_retries),
                    "--backoff-seconds",
                    str(args.backoff_seconds),
                    "--resume",
                    "--mark-empty-complete",
                    "--out",
                    str(out),
                ],
                manifest=manifest,
                rows=manifest_rows,
                keep_going=args.keep_going,
            )
        fetched.append(out)

    return fetched


def build_sec_enriched_signals(
    args: argparse.Namespace,
    *,
    py: str,
    labeled: Path,
    queries_file: Path,
    manifest: Path,
    manifest_rows: list[dict],
) -> Path:
    sec_sources = [path for path in args.sec_sources if path.exists()]
    if args.fetch_sec:
        if not args.sec_user_agent:
            raise SystemExit(
                "SEC fetch requested but no SEC user agent was provided. "
                "Use --sec-user-agent or set SEC_USER_AGENT."
            )
        fetched_sec = args.work_dir / f"sec_{args.start}_{args.end}.jsonl"
        tickers = read_queries(queries_file)
        run_step(
            "fetch_sec_sources",
            [
                py,
                "-m",
                "scripts.fetch_sec_intelligence_sources",
                "--tickers",
                *tickers,
                "--start",
                args.start,
                "--end",
                args.end,
                "--forms",
                *args.sec_forms,
                "--user-agent",
                args.sec_user_agent,
                "--sleep-seconds",
                str(args.sec_sleep_seconds),
                "--out",
                str(fetched_sec),
            ],
            manifest=manifest,
            rows=manifest_rows,
            keep_going=args.keep_going,
            skip_if_exists=fetched_sec if args.skip_existing else None,
        )
        if fetched_sec.exists():
            sec_sources.append(fetched_sec)

    sec_sources = [path for path in sec_sources if path.exists()]
    if not sec_sources:
        return labeled

    combined_sec = sec_sources[0]
    if len(sec_sources) > 1:
        combined_sec = write_combined_jsonl(sec_sources, args.work_dir / "sec_sources_combined.jsonl")

    sec_features = args.work_dir / "historical_sec_features.parquet"
    labeled_sec = args.work_dir / "historical_panel_labeled_sec.parquet"
    run_step(
        "build_sec_features",
        [
            py,
            "-m",
            "scripts.build_historical_sec_features",
            "--sec-sources",
            str(combined_sec),
            "--signals",
            str(labeled),
            "--features-out",
            str(sec_features),
            "--joined-out",
            str(labeled_sec),
            "--windows",
            *[str(w) for w in args.windows],
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
        skip_if_exists=labeled_sec if args.skip_existing else None,
    )
    return labeled_sec if labeled_sec.exists() else labeled


def main() -> None:
    args = parse_args()
    py = sys.executable
    args.work_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.work_dir / "stress_manifest.csv"
    manifest_rows: list[dict] = []

    validate_signal_coverage(args)

    seed = args.work_dir / "historical_panel_seed.parquet"
    labeled = args.work_dir / "historical_panel_labeled.parquet"
    queries_file = args.queries_file or args.work_dir / "stress_tickers.txt"

    build_seed_cmd = [
        py,
        "-m",
        "scripts.build_historical_intelligence_panel_seed",
        "--signals",
        str(args.signals),
        "--out",
        str(seed),
        "--start",
        args.start,
        "--end",
        args.end,
        "--top-n-per-date",
        str(args.top_n_per_date),
    ]
    if args.ticker_col:
        build_seed_cmd.extend(["--ticker-col", args.ticker_col])
    if args.date_col:
        build_seed_cmd.extend(["--date-col", args.date_col])
    if args.rank_col:
        build_seed_cmd.extend(["--rank-col", args.rank_col])
    if args.min_rank_value is not None:
        build_seed_cmd.extend(["--min-rank-value", str(args.min_rank_value)])
    if args.max_dates is not None:
        build_seed_cmd.extend(["--max-dates", str(args.max_dates)])
    run_step(
        "build_historical_seed",
        build_seed_cmd,
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
        skip_if_exists=seed if args.skip_existing else None,
    )

    if not args.queries_file:
        write_queries_from_seed(seed, queries_file, args.ticker_col)

    label_cmd = [
        py,
        "-m",
        "scripts.build_outcome_labels",
        "--signals",
        str(seed),
        "--out",
        str(labeled),
        "--download-period",
        args.download_period,
        "--horizons",
        *[str(h) for h in args.horizons],
        "--success-horizon",
        str(args.success_horizon),
    ]
    if args.download_prices:
        label_cmd.append("--download-prices")
    if args.ticker_col:
        label_cmd.extend(["--ticker-col", args.ticker_col])
    if args.date_col:
        label_cmd.extend(["--date-col", args.date_col])
    run_step(
        "build_outcome_labels",
        label_cmd,
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
        skip_if_exists=labeled if args.skip_existing else None,
    )

    training_signals = build_sec_enriched_signals(
        args,
        py=py,
        labeled=labeled,
        queries_file=queries_file,
        manifest=manifest,
        manifest_rows=manifest_rows,
    )

    news_sources = list(args.news_sources)
    if args.fetch_news:
        news_sources.extend(
            fetch_chunks(
                args,
                py=py,
                queries_file=queries_file,
                manifest=manifest,
                manifest_rows=manifest_rows,
            )
        )
    news_sources = [path for path in news_sources if path.exists()]
    if not news_sources:
        raise SystemExit("No historical news sources available. Provide --news-sources or use --fetch-news.")

    run_step(
        "train_walk_forward_grid",
        [
            py,
            "-m",
            "scripts.run_intelligence_training_batch",
            "--news-sources",
            *[str(path) for path in news_sources],
            "--work-dir",
            str(args.work_dir),
            "--signals",
            str(training_signals),
            "--target-col",
            f"success_{args.success_horizon}d",
            "--return-cols",
            *args.return_cols,
            "--top-ns",
            *[str(n) for n in args.top_ns],
            "--windows",
            *[str(w) for w in args.windows],
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
            "--test-days",
            str(args.test_days),
            "--step-days",
            str(args.step_days),
            "--min-test-rows",
            str(args.min_test_rows),
            "--iterations",
            str(args.iterations),
            "--min-relevance-score",
            str(args.min_relevance_score),
            "--cash",
            str(args.cash),
            "--score-sentiment",
            "--sentiment-backend",
            args.sentiment_backend,
            "--sentiment-batch-size",
            str(args.sentiment_batch_size),
            "--nlp-device",
            args.nlp_device,
            "--keep-going",
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
    )

    ranked = args.work_dir / "all_monte_carlo_ranked.csv"
    run_step(
        "summarize_training_run",
        [
            py,
            "-m",
            "scripts.summarize_intelligence_training_run",
            "--run-dir",
            str(args.work_dir),
            "--out",
            str(ranked),
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=True,
    )

    equity_out = args.work_dir / f"equity_spaghetti_{args.equity_return_col}_top{args.equity_top_n}"
    run_step(
        "simulate_best_equity_spaghetti",
        [
            py,
            "-m",
            "scripts.simulate_intelligence_equity_curves",
            "--run-dir",
            str(args.work_dir),
            "--ranked-summary",
            str(ranked),
            "--return-col",
            args.equity_return_col,
            "--top-n",
            str(args.equity_top_n),
            "--cash",
            str(args.cash),
            "--iterations",
            str(args.equity_iterations),
            "--block-size",
            "3",
            "--spaghetti-paths",
            "250",
            "--out-dir",
            str(equity_out),
        ],
        manifest=manifest,
        rows=manifest_rows,
        keep_going=args.keep_going,
    )

    print("\nHistorical stress run complete.")
    print(f"Manifest: {manifest}")
    print(f"Ranked Monte Carlo: {ranked}")
    print(f"Equity/spaghetti outputs: {equity_out}")


if __name__ == "__main__":
    main()
