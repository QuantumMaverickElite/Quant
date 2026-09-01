from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_NEWS_SOURCES = [
    "data/intelligence/historical/raw/news_eval_2025_2026_merged_full_scored.jsonl",
    "data/intelligence/historical/raw/sec_eval_2025_2026.jsonl",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch an unattended long intelligence ML training run.")
    parser.add_argument("--signals", default="outputs/signals/mean_reversion_latest_with_intelligence.parquet")
    parser.add_argument("--news-sources", nargs="+", default=DEFAULT_NEWS_SOURCES)
    parser.add_argument("--work-root", default="outputs/intelligence/training_runs")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2023-12-31")
    parser.add_argument("--top-n-per-date", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument("--equity-iterations", type=int, default=25_000)
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--sentiment-backend", choices=["finbert", "heuristic", "auto"], default="finbert")
    parser.add_argument("--sentiment-batch-size", type=int, default=16)
    parser.add_argument("--cargo-release", action="store_true", help="Run cargo build --release first if Cargo.toml exists.")
    parser.add_argument("--dry-run", action="store_true", help="Write the run script but do not launch it.")
    parser.add_argument("--profile", choices=["short_horizon", "balanced"], default="short_horizon")
    return parser.parse_args()


def quote_cmd(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def require_paths(paths: list[str], *, label: str) -> list[Path]:
    existing: list[Path] = []
    missing: list[Path] = []
    for value in paths:
        path = Path(value)
        if path.exists():
            existing.append(path)
        else:
            missing.append(path)
    if missing:
        print(f"Missing {label}:")
        for path in missing:
            print(f"  {path}")
    return existing


def profile_args(profile: str) -> dict[str, list[str]]:
    if profile == "balanced":
        return {
            "horizons": ["1", "3", "5", "10", "20"],
            "success_horizon": ["10"],
            "return_cols": ["next_3d_return", "next_5d_return", "next_10d_return", "next_20d_return"],
            "top_ns": ["5", "10", "15", "20", "30"],
            "train_days": ["126", "252"],
            "embargo_days": ["5", "10", "20"],
            "alpha": ["3", "10", "30"],
            "model_types": ["logistic", "ridge"],
            "min_train_rows": ["100", "200"],
            "test_days": ["5"],
            "step_days": ["5"],
        }
    return {
        "horizons": ["1", "3", "5", "10"],
        "success_horizon": ["5"],
        "return_cols": ["next_1d_return", "next_3d_return", "next_5d_return", "next_10d_return"],
        "top_ns": ["3", "5", "10", "15", "20"],
        "train_days": ["63", "126", "252"],
        "embargo_days": ["3", "5", "10"],
        "alpha": ["1", "3", "10", "30"],
        "model_types": ["logistic", "ridge"],
        "min_train_rows": ["100", "200"],
        "test_days": ["3"],
        "step_days": ["3"],
    }


def write_run_script(args: argparse.Namespace, *, work_dir: Path, news_sources: list[Path]) -> Path:
    p = profile_args(args.profile)
    script = work_dir / "run_long_training.sh"
    py = sys.executable
    train_cmd = [
        py,
        "scripts/run_historical_intelligence_stress.py",
        "--signals",
        args.signals,
        "--start",
        args.start,
        "--end",
        args.end,
        "--work-dir",
        str(work_dir),
        "--top-n-per-date",
        str(args.top_n_per_date),
        "--horizons",
        *p["horizons"],
        "--success-horizon",
        *p["success_horizon"],
        "--news-sources",
        *[str(path) for path in news_sources],
        "--score-sentiment",
        "--sentiment-backend",
        args.sentiment_backend,
        "--sentiment-batch-size",
        str(args.sentiment_batch_size),
        "--nlp-device",
        args.nlp_device,
        "--iterations",
        str(args.iterations),
        "--equity-iterations",
        str(args.equity_iterations),
        "--return-cols",
        *p["return_cols"],
        "--top-ns",
        *p["top_ns"],
        "--train-days-list",
        *p["train_days"],
        "--embargo-days-list",
        *p["embargo_days"],
        "--alpha-list",
        *p["alpha"],
        "--model-types",
        *p["model_types"],
        "--min-train-rows-list",
        *p["min_train_rows"],
        "--test-days",
        *p["test_days"],
        "--step-days",
        *p["step_days"],
        "--min-test-rows",
        "5",
        "--skip-existing",
        "--keep-going",
    ]

    lines = [
        "#!/usr/bin/env bash",
        "set -u",
        "set -o pipefail",
        f"RUN_DIR={shlex.quote(str(work_dir))}",
        'mkdir -p "$RUN_DIR"',
        'echo "started_at=$(date -Is)" | tee "$RUN_DIR/status.txt"',
        'echo "host=$(hostname)" | tee -a "$RUN_DIR/status.txt"',
        f"echo {shlex.quote('profile=' + args.profile)} | tee -a \"$RUN_DIR/status.txt\"",
        f"echo {shlex.quote('python=' + py)} | tee -a \"$RUN_DIR/status.txt\"",
        f"{quote_cmd([py, '-m', 'compileall', '-q', 'src', 'scripts'])}",
    ]
    if args.cargo_release:
        lines.extend(
            [
                'if [ -f Cargo.toml ]; then',
                '  echo "cargo_build_release_start=$(date -Is)" | tee -a "$RUN_DIR/status.txt"',
                "  cargo build --release",
                '  echo "cargo_build_release_done=$(date -Is)" | tee -a "$RUN_DIR/status.txt"',
                "fi",
            ]
        )
    lines.extend(
        [
            'echo "training_start=$(date -Is)" | tee -a "$RUN_DIR/status.txt"',
            quote_cmd(train_cmd),
            "rc=$?",
            'echo "training_done=$(date -Is)" | tee -a "$RUN_DIR/status.txt"',
            'echo "returncode=$rc" | tee -a "$RUN_DIR/status.txt"',
            "exit $rc",
            "",
        ]
    )
    script.write_text("\n".join(lines), encoding="utf-8")
    script.chmod(0o755)
    return script


def main() -> None:
    args = parse_args()
    run_name = args.run_name.strip()
    if not run_name:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"long_v5_7_{args.profile}_{args.start}_{args.end}_{stamp}".replace(":", "").replace("/", "_")
    work_dir = Path(args.work_root) / run_name
    work_dir.mkdir(parents=True, exist_ok=True)

    if not Path(args.signals).exists():
        raise SystemExit(f"Signals file not found: {args.signals}")

    required_scripts = [
        "scripts/run_historical_intelligence_stress.py",
        "scripts/run_intelligence_training_batch.py",
        "scripts/build_historical_news_features.py",
        "scripts/merge_historical_sources.py",
        "scripts/score_historical_news_sentiment.py",
        "scripts/walk_forward_intelligence_calibration.py",
        "scripts/monte_carlo_walk_forward_predictions.py",
        "scripts/summarize_intelligence_training_run.py",
    ]
    missing_scripts = [path for path in required_scripts if not Path(path).exists()]
    if missing_scripts:
        raise SystemExit("Missing required scripts:\n" + "\n".join(f"  {path}" for path in missing_scripts))

    news_sources = require_paths(args.news_sources, label="news sources")
    if not news_sources:
        raise SystemExit("No usable news sources found.")

    script = write_run_script(args, work_dir=work_dir, news_sources=news_sources)
    log_path = work_dir / "long_training.log"
    pid_path = work_dir / "long_training.pid"

    print(f"Run dir: {work_dir}")
    print(f"Run script: {script}")
    print(f"Log: {log_path}")

    if args.dry_run:
        print("Dry run only; not launched.")
        return

    log = log_path.open("ab")
    process = subprocess.Popen(
        ["bash", str(script)],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        cwd=Path.cwd(),
        env=os.environ.copy(),
    )
    pid_path.write_text(str(process.pid) + "\n", encoding="utf-8")
    print(f"Launched PID: {process.pid}")
    print(f"Monitor: python scripts/monitor_long_intelligence_training.py --run-dir {work_dir}")


if __name__ == "__main__":
    main()
