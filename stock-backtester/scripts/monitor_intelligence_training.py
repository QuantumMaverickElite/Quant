from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor intelligence ML training progress and write trajectory reports.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--out-csv", type=Path)
    parser.add_argument("--plots-dir", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--return-col", default="next_5d_return")
    parser.add_argument("--top-n", type=int, default=5)
    return parser.parse_args()


def read_manifest(run_dir: Path) -> pd.DataFrame:
    candidates = [run_dir / "manifest.csv", run_dir / "pool_manifest.csv"]
    frames: list[pd.DataFrame] = []
    for path in candidates:
        if path.exists():
            frame = pd.read_csv(path)
            frame["manifest_file"] = path.name
            frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["step", "returncode", "elapsed_seconds", "command", "manifest_file"])
    out = pd.concat(frames, ignore_index=True)
    out["step_index"] = range(len(out))
    return out


def read_monte_carlo_files(run_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted(run_dir.glob("*_monte_carlo.csv")):
        try:
            frame = pd.read_csv(path)
        except Exception as exc:
            print(f"Skipping unreadable file {path}: {exc}")
            continue
        frame["config"] = path.name.replace("_monte_carlo.csv", "")
        frame["source_file"] = path.name
        frame["file_mtime"] = path.stat().st_mtime
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_progress_snapshot(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest = read_manifest(run_dir)
    mc = read_monte_carlo_files(run_dir)
    if mc.empty:
        return manifest, mc, pd.DataFrame()

    summary_rows: list[dict] = []
    for idx, path in enumerate(sorted(run_dir.glob("*_monte_carlo.csv"))):
        frame = pd.read_csv(path)
        frame["config"] = path.name.replace("_monte_carlo.csv", "")
        frame["completed_config_count"] = idx + 1
        frame["file_mtime"] = path.stat().st_mtime
        best = frame.sort_values(
            [col for col in ["cash_ml_minus_baseline", "prob_ml_beats_baseline"] if col in frame.columns],
            ascending=False,
        ).head(1)
        if best.empty:
            continue
        row = best.iloc[0].to_dict()
        row["source_file"] = path.name
        summary_rows.append(row)
    trajectory = pd.DataFrame(summary_rows)
    if not trajectory.empty:
        trajectory = trajectory.sort_values("file_mtime")
        trajectory["monitor_step"] = range(1, len(trajectory) + 1)
        trajectory["best_cash_ml_minus_baseline_so_far"] = trajectory["cash_ml_minus_baseline"].cummax()
        if "prob_ml_beats_baseline" in trajectory.columns:
            trajectory["best_prob_ml_beats_baseline_so_far"] = trajectory["prob_ml_beats_baseline"].cummax()
    return manifest, mc, trajectory


def write_plots(mc: pd.DataFrame, trajectory: pd.DataFrame, plots_dir: Path, *, return_col: str, top_n: int, top: int) -> None:
    plots_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable; skipped plots: {exc}")
        return

    if not trajectory.empty:
        plt.figure(figsize=(11, 6))
        plt.plot(trajectory["monitor_step"], trajectory["cash_ml_minus_baseline"], marker="o", label="config best lift")
        plt.plot(
            trajectory["monitor_step"],
            trajectory["best_cash_ml_minus_baseline_so_far"],
            marker=".",
            label="best lift so far",
        )
        plt.axhline(0, color="black", linewidth=0.8)
        plt.title("ML Lift Trajectory")
        plt.xlabel("completed Monte Carlo config")
        plt.ylabel("cash ML minus baseline")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_dir / "ml_lift_trajectory.png", dpi=150)
        plt.close()

    if not mc.empty and {"return_col", "top_n", "cash_ml_minus_baseline"}.issubset(mc.columns):
        focus = mc[(mc["return_col"].eq(return_col)) & (mc["top_n"].eq(top_n))].copy()
        focus = focus.sort_values("cash_ml_minus_baseline", ascending=False).head(top)
        if not focus.empty:
            labels = focus["config"].astype(str).str.replace("wf_", "", regex=False)
            plt.figure(figsize=(12, max(5, 0.35 * len(focus))))
            plt.barh(labels[::-1], focus["cash_ml_minus_baseline"].iloc[::-1])
            plt.axvline(0, color="black", linewidth=0.8)
            plt.title(f"Top ML Lift Configs ({return_col}, top {top_n})")
            plt.xlabel("cash ML minus baseline")
            plt.tight_layout()
            plt.savefig(plots_dir / f"top_lift_{return_col}_top{top_n}.png", dpi=150)
            plt.close()


def print_status(manifest: pd.DataFrame, mc: pd.DataFrame, trajectory: pd.DataFrame, *, top: int) -> None:
    completed_steps = int((manifest.get("returncode", pd.Series(dtype=float)) == 0).sum()) if not manifest.empty else 0
    failed_steps = int((manifest.get("returncode", pd.Series(dtype=float)) != 0).sum()) if not manifest.empty else 0
    print(f"manifest steps: {len(manifest)} completed={completed_steps} nonzero={failed_steps}")
    print(f"monte carlo files: {mc['source_file'].nunique() if not mc.empty else 0}")
    if trajectory.empty:
        print("No trajectory yet.")
        return
    display = [
        "monitor_step",
        "config",
        "return_col",
        "top_n",
        "cash_ml_minus_baseline",
        "prob_ml_beats_baseline",
        "best_cash_ml_minus_baseline_so_far",
    ]
    print(trajectory[[c for c in display if c in trajectory.columns]].tail(top).round(4).to_string(index=False))


def run_once(args: argparse.Namespace) -> None:
    manifest, mc, trajectory = build_progress_snapshot(args.run_dir)
    out_csv = args.out_csv or args.run_dir / "training_monitor_trajectory.csv"
    if not trajectory.empty:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        trajectory.to_csv(out_csv, index=False)
        print(f"Saved trajectory: {out_csv}")
    if args.plots_dir:
        write_plots(mc, trajectory, args.plots_dir, return_col=args.return_col, top_n=args.top_n, top=args.top)
        print(f"Saved plots: {args.plots_dir}")
    print_status(manifest, mc, trajectory, top=args.top)


def main() -> None:
    args = parse_args()
    while True:
        run_once(args)
        if not args.watch:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
