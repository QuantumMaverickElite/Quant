from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path


def parse_float_list(values: list[str]) -> list[float]:
    return [float(value) for value in values]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run unattended historical intelligence ML training and Monte Carlo grid.")
    parser.add_argument("--news-sources", nargs="+", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--signals", type=Path, default=Path("outputs/intelligence/calibration/historical_panel_labeled_sec.parquet"))
    parser.add_argument("--intelligence-features", type=Path, default=Path("outputs/intelligence/intelligence_features_opportunity_scored.csv"))
    parser.add_argument("--event-features", type=Path, default=Path("outputs/intelligence/contextual_event_features.csv"))
    parser.add_argument("--target-col", default="success_10d")
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--windows", nargs="+", type=int, default=[1, 7, 30, 90])
    parser.add_argument("--train-days-list", nargs="+", type=int, default=[90, 126, 252])
    parser.add_argument("--embargo-days-list", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--alpha-list", nargs="+", default=["1.0", "3.0", "10.0", "30.0"])
    parser.add_argument("--model-types", nargs="+", choices=["logistic", "ridge"], default=["logistic", "ridge"])
    parser.add_argument("--min-train-rows-list", nargs="+", type=int, default=[100, 200])
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--min-test-rows", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--min-relevance-score", type=float)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--score-sentiment", action="store_true")
    parser.add_argument("--sentiment-backend", choices=["finbert", "heuristic", "auto"], default="finbert")
    parser.add_argument("--sentiment-batch-size", type=int, default=16)
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--keep-going", action="store_true")
    return parser.parse_args()


def run_step(name: str, cmd: list[str], *, work_dir: Path, manifest_rows: list[dict], keep_going: bool) -> None:
    started = time.time()
    print("\n" + "=" * 80)
    print(name)
    print(" ".join(cmd))
    completed = subprocess.run(cmd, text=True)
    elapsed = time.time() - started
    manifest_rows.append(
        {
            "step": name,
            "returncode": completed.returncode,
            "elapsed_seconds": round(elapsed, 3),
            "command": " ".join(cmd),
        }
    )
    write_manifest(work_dir / "manifest.csv", manifest_rows)
    if completed.returncode != 0 and not keep_going:
        raise SystemExit(completed.returncode)


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["step", "returncode", "elapsed_seconds", "command"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def path_for_float(value: float) -> str:
    return str(value).replace(".", "p").replace("-", "m")


def main() -> None:
    args = parse_args()
    work_dir = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict] = []
    py = sys.executable
    alpha_values = parse_float_list(args.alpha_list)

    merged_sources = work_dir / "historical_news_merged.jsonl"
    merge_cmd = [
        py,
        "-m",
        "scripts.merge_historical_sources",
        "--inputs",
        *[str(path) for path in args.news_sources],
        "--out",
        str(merged_sources),
        "--audit-csv",
        str(work_dir / "historical_news_merge_audit.csv"),
    ]
    if args.min_relevance_score is not None:
        merge_cmd.extend(["--min-relevance-score", str(args.min_relevance_score)])
    run_step(
        "merge_sources",
        merge_cmd,
        work_dir=work_dir,
        manifest_rows=manifest_rows,
        keep_going=args.keep_going,
    )

    news_sources_for_features = merged_sources
    if args.score_sentiment:
        scored_sources = work_dir / "historical_news_merged_scored.jsonl"
        run_step(
            "score_sentiment",
            [
                py,
                "-m",
                "scripts.score_historical_news_sentiment",
                "--input",
                str(merged_sources),
                "--out",
                str(scored_sources),
                "--backend",
                args.sentiment_backend,
                "--batch-size",
                str(args.sentiment_batch_size),
                "--checkpoint-every",
                "250",
                "--nlp-device",
                args.nlp_device,
            ],
            work_dir=work_dir,
            manifest_rows=manifest_rows,
            keep_going=args.keep_going,
        )
        news_sources_for_features = scored_sources

    news_features = work_dir / "historical_news_features.parquet"
    joined_signals = work_dir / "historical_panel_labeled_sec_news.parquet"
    run_step(
        "build_news_features",
        [
            py,
            "-m",
            "scripts.build_historical_news_features",
            "--news-sources",
            str(news_sources_for_features),
            "--signals",
            str(args.signals),
            "--features-out",
            str(news_features),
            "--joined-out",
            str(joined_signals),
            "--windows",
            *[str(w) for w in args.windows],
        ],
        work_dir=work_dir,
        manifest_rows=manifest_rows,
        keep_going=args.keep_going,
    )

    calibration_dataset = work_dir / "historical_intelligence_panel_sec_news.parquet"
    run_step(
        "build_calibration_dataset",
        [
            py,
            "-m",
            "scripts.build_intelligence_calibration_dataset",
            "--labeled-signals",
            str(joined_signals),
            "--intelligence-features",
            str(args.intelligence_features),
            "--event-features",
            str(args.event_features),
            "--out",
            str(calibration_dataset),
        ],
        work_dir=work_dir,
        manifest_rows=manifest_rows,
        keep_going=args.keep_going,
    )

    for model_type in args.model_types:
        for train_days in args.train_days_list:
            for embargo_days in args.embargo_days_list:
                for min_train_rows in args.min_train_rows_list:
                    for alpha in alpha_values:
                        stem = (
                            f"wf_{model_type}_train{train_days}_embargo{embargo_days}"
                            f"_min{min_train_rows}_alpha{path_for_float(alpha)}"
                        )
                        predictions = work_dir / f"{stem}_predictions.parquet"
                        summary = work_dir / f"{stem}_summary.csv"
                        mc_summary = work_dir / f"{stem}_monte_carlo.csv"
                        run_step(
                            f"walk_forward_{stem}",
                            [
                                py,
                                "-m",
                                "scripts.walk_forward_intelligence_calibration",
                                "--dataset",
                                str(calibration_dataset),
                                "--target-col",
                                args.target_col,
                                "--return-cols",
                                *args.return_cols,
                                "--top-ns",
                                *[str(n) for n in args.top_ns],
                                "--predictions-out",
                                str(predictions),
                                "--summary-out",
                                str(summary),
                                "--model-type",
                                model_type,
                                "--alpha",
                                str(alpha),
                                "--train-days",
                                str(train_days),
                                "--test-days",
                                str(args.test_days),
                                "--step-days",
                                str(args.step_days),
                                "--embargo-days",
                                str(embargo_days),
                                "--min-train-rows",
                                str(min_train_rows),
                                "--min-test-rows",
                                str(args.min_test_rows),
                                "--cash",
                                str(args.cash),
                            ],
                            work_dir=work_dir,
                            manifest_rows=manifest_rows,
                            keep_going=args.keep_going,
                        )
                        if not predictions.exists():
                            continue
                        run_step(
                            f"monte_carlo_{stem}",
                            [
                                py,
                                "-m",
                                "scripts.monte_carlo_walk_forward_predictions",
                                "--predictions",
                                str(predictions),
                                "--return-cols",
                                *args.return_cols,
                                "--top-ns",
                                *[str(n) for n in args.top_ns],
                                "--iterations",
                                str(args.iterations),
                                "--cash",
                                str(args.cash),
                                "--out",
                                str(mc_summary),
                            ],
                            work_dir=work_dir,
                            manifest_rows=manifest_rows,
                            keep_going=args.keep_going,
                        )

    print("\nBatch complete.")
    print(f"Manifest: {work_dir / 'manifest.csv'}")


if __name__ == "__main__":
    main()
