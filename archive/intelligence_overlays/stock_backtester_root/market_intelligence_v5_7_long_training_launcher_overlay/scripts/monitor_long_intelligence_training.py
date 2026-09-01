from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor a detached long intelligence training run.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--tail-lines", type=int, default=80)
    return parser.parse_args()


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


def print_csv_tail(path: Path, n: int = 10) -> None:
    if not path.exists():
        return
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        print(f"\nCould not read {path}: {exc}")
        return
    print(f"\n{path}")
    print(f"shape={df.shape}")
    print(df.tail(n).to_string(index=False))


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir
    pid_path = run_dir / "long_training.pid"
    status_path = run_dir / "status.txt"
    log_path = run_dir / "long_training.log"
    manifest_path = run_dir / "stress_manifest.csv"
    ranked_path = run_dir / "all_monte_carlo_ranked.csv"

    print(f"Run dir: {run_dir}")
    if pid_path.exists():
        raw = pid_path.read_text(encoding="utf-8").strip()
        try:
            pid = int(raw)
            print(f"PID: {pid} alive={process_alive(pid)}")
        except ValueError:
            print(f"PID file contained: {raw!r}")
    else:
        print("PID file not found.")

    if status_path.exists():
        print("\nstatus.txt")
        print(status_path.read_text(encoding="utf-8", errors="replace").strip())

    print_csv_tail(manifest_path)
    print_csv_tail(ranked_path, n=20)

    print(f"\nLast {args.tail_lines} log lines:")
    for line in tail(log_path, args.tail_lines):
        print(line)


if __name__ == "__main__":
    main()
