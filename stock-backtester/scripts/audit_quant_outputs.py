#!/usr/bin/env python3
"""Audit quant project outputs and produce a cleanup/archive plan.

Default is dry-run. This script does not delete files unless --delete is passed.
It is intentionally conservative: it classifies files and writes a CSV plan so you can
review before removing anything.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_ROOTS = ["outputs"]

ALWAYS_KEEP_PATTERNS = [
    "all_monte_carlo_ranked.csv",
    "stress_manifest.csv",
    "manifest.csv",
    "status.txt",
    "run_long_training.sh",
    "*_summary.csv",
    "equity_simulation_summary.csv",
    "policy_strength_sweep_summary.csv",
    "ml_policy_permutation_summary.csv",
    "README.md",
    "*.md",
    "*.json",
]

DELETE_CANDIDATE_PATTERNS = [
    "*bootstrap_equity_paths*.csv",
    "*spaghetti*paths*.csv",
    "*curve*.csv",
    "*curves*.csv",
    "*trial*.csv",
    "*trials*.csv",
    "frame_*.csv",
    "frame_*.json",
    "frame_*.parquet",
    "*.mp4",
]

ARCHIVE_CANDIDATE_PATTERNS = [
    "*.jsonl",
    "*.log",
    "*.png",
    "*.html",
    "*.parquet",
    "*.npz",
    "*.zarr",
]

RUN_SUMMARY_NAMES = {
    "all_monte_carlo_ranked.csv",
    "stress_manifest.csv",
    "manifest.csv",
    "status.txt",
}


def human_size(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{n} B"


def match_any(name: str, patterns: Iterable[str]) -> str | None:
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return pat
    return None


def file_age_days(path: Path) -> float:
    try:
        return max(0.0, (os.path.getmtime(".") - path.stat().st_mtime) / 86400.0)
    except Exception:
        return 0.0


def has_ranked_summary(directory: Path) -> bool:
    cur = directory
    for _ in range(6):
        if (cur / "all_monte_carlo_ranked.csv").exists():
            return True
        if cur.parent == cur:
            break
        cur = cur.parent
    return False


def classify(path: Path, root: Path, large_mb: float, aggressive: bool) -> tuple[str, str]:
    name = path.name
    size = path.stat().st_size
    size_mb = size / (1024 * 1024)

    keep_match = match_any(name, ALWAYS_KEEP_PATTERNS)
    del_match = match_any(name, DELETE_CANDIDATE_PATTERNS)
    arch_match = match_any(name, ARCHIVE_CANDIDATE_PATTERNS)

    if keep_match:
        return "keep", f"matches keep pattern {keep_match}"

    if del_match:
        return "delete_candidate", f"bulky/regenerable pattern {del_match}"

    # Raw provider payloads are useful only until compact features/scored features exist.
    if name.endswith(".jsonl"):
        return "archive_candidate", "raw/source JSONL; archive or compact after feature extraction"

    # Parquet predictions/features can be valuable, but too many should be compacted.
    if name.endswith("_predictions.parquet"):
        return "archive_candidate", "prediction parquet; keep only top configs locally"

    if arch_match:
        return "archive_candidate", f"matches archive pattern {arch_match}"

    if size_mb >= large_mb:
        if aggressive and has_ranked_summary(path.parent):
            return "archive_candidate", f"large file {human_size(size)} inside completed run"
        return "review_large", f"large file {human_size(size)}"

    # Failed run heuristic: run folder has status/manifest but no ranked summary.
    if name in {"historical_panel_seed.parquet", "historical_panel_labeled.parquet"} and not has_ranked_summary(path.parent):
        return "review_failed_run", "panel artifact in run without ranked summary nearby"

    return "keep_small_or_review", "small/unclassified"


@dataclass
class Row:
    action: str
    size_bytes: int
    size_human: str
    path: str
    reason: str


def scan(roots: list[Path], large_mb: float, aggressive: bool) -> list[Row]:
    rows: list[Row] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            action, reason = classify(p, root, large_mb, aggressive)
            rows.append(Row(action, size, human_size(size), str(p), reason))
    rows.sort(key=lambda r: (r.action, r.size_bytes), reverse=True)
    return rows


def write_csv(rows: list[Row], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["action", "size_bytes", "size_human", "path", "reason"])
        w.writeheader()
        for r in rows:
            w.writerow(r.__dict__)


def summarize(rows: list[Row]) -> None:
    totals: dict[str, tuple[int, int]] = {}
    for r in rows:
        count, size = totals.get(r.action, (0, 0))
        totals[r.action] = (count + 1, size + r.size_bytes)
    print("\nCleanup plan summary")
    print("-" * 72)
    for action, (count, size) in sorted(totals.items(), key=lambda kv: kv[1][1], reverse=True):
        print(f"{action:24s} files={count:7d} size={human_size(size):>12s}")
    print("-" * 72)
    print(f"Total scanned: files={len(rows):,} size={human_size(sum(r.size_bytes for r in rows))}")

    print("\nLargest delete/archive/review candidates")
    candidates = [r for r in rows if r.action in {"delete_candidate", "archive_candidate", "review_large", "review_failed_run"}]
    for r in sorted(candidates, key=lambda x: x.size_bytes, reverse=True)[:40]:
        print(f"{r.action:20s} {r.size_human:>10s}  {r.path}  # {r.reason}")


def delete_candidates(rows: list[Row], yes: bool) -> None:
    targets = [Path(r.path) for r in rows if r.action == "delete_candidate"]
    if not targets:
        print("No delete candidates.")
        return
    print(f"Delete candidates: {len(targets):,}")
    if not yes:
        print("Refusing to delete without --yes. Re-run with --delete --yes after reviewing the CSV plan.")
        return
    for p in targets:
        try:
            p.unlink()
            print(f"deleted {p}")
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"failed_delete {p}: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS, help="Folders to scan. Default: outputs")
    ap.add_argument("--out", default="outputs/storage_audit/cleanup_plan.csv", help="CSV cleanup plan path")
    ap.add_argument("--large-mb", type=float, default=100.0, help="Flag unclassified files above this size")
    ap.add_argument("--aggressive", action="store_true", help="More aggressively mark large completed-run files as archive candidates")
    ap.add_argument("--delete", action="store_true", help="Delete delete_candidate files only")
    ap.add_argument("--yes", action="store_true", help="Required with --delete")
    args = ap.parse_args()

    roots = [Path(r) for r in args.roots]
    rows = scan(roots, args.large_mb, args.aggressive)
    out = Path(args.out)
    write_csv(rows, out)
    summarize(rows)
    print(f"\nWrote plan: {out}")
    print("Default is dry-run. Review the CSV before deleting anything.")

    if args.delete:
        delete_candidates(rows, args.yes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
