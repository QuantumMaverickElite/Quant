#!/usr/bin/env python3
"""Compact a finished intelligence training run into a small reproducible artifact bundle.

This copies summaries, manifests, configs, log tails, and selected top prediction files.
It does not delete anything unless --delete-heavy-local --yes is explicitly passed.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import gzip
import hashlib
import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None

KEEP_NAMES = {
    "all_monte_carlo_ranked.csv",
    "stress_manifest.csv",
    "manifest.csv",
    "status.txt",
    "run_long_training.sh",
    "equity_simulation_summary.csv",
    "policy_strength_sweep_summary.csv",
    "ml_policy_permutation_summary.csv",
}

KEEP_PATTERNS = [
    "*_summary.csv",
    "*ranked*.csv",
    "*manifest*.csv",
    "*.md",
    "*.json",
]

HEAVY_PATTERNS = [
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
    "*.jsonl",
]


def human_size(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f} {u}" if u != "B" else f"{int(x)} B"
        x /= 1024
    return f"{n} B"


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def match_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def safe_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_log_tail(src: Path, dst: Path, tail_bytes: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    size = src.stat().st_size
    with src.open("rb") as f:
        if size > tail_bytes:
            f.seek(max(0, size - tail_bytes))
            data = f.read()
            marker = f"\n--- LOG TAIL ONLY: original_size={size} bytes, tail_bytes={tail_bytes} ---\n".encode()
            dst.write_bytes(marker + data)
        else:
            dst.write_bytes(f.read())


def read_top_configs(ranked: Path, top_n: int) -> list[str]:
    if not ranked.exists() or top_n <= 0:
        return []
    if pd is None:
        configs: list[str] = []
        with ranked.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cfg = row.get("config")
                if cfg and cfg not in configs:
                    configs.append(cfg)
                if len(configs) >= top_n:
                    break
        return configs
    df = pd.read_csv(ranked)
    if "config" not in df.columns:
        return []
    configs = []
    for cfg in df["config"].dropna().astype(str).tolist():
        if cfg not in configs:
            configs.append(cfg)
        if len(configs) >= top_n:
            break
    return configs


def should_keep_file(path: Path, run_dir: Path, top_configs: set[str], include_plots: bool, include_raw: bool) -> tuple[bool, str]:
    rel = path.relative_to(run_dir)
    name = path.name

    if name in KEEP_NAMES or match_any(name, KEEP_PATTERNS):
        return True, "summary/manifest/config"

    if name.endswith(".log"):
        return True, "log_tail"

    if include_plots and name.endswith((".png", ".html")):
        return True, "plot/report"

    if include_raw and name.endswith(".jsonl"):
        return True, "raw_included_explicitly"

    if name.endswith("_predictions.parquet"):
        stem = name.removesuffix("_predictions.parquet")
        if stem in top_configs:
            return True, "top_config_prediction"
        return False, "non_top_prediction"

    # Keep selected equity/policy/permutation summaries inside subfolders.
    if any(part.startswith(("equity_spaghetti", "policy_strength", "permutation")) for part in rel.parts):
        if name.endswith("_summary.csv") or name in KEEP_NAMES or name == "deterministic_equity.csv" or name == "portfolio_returns.csv":
            return True, "validation_summary"

    return False, "not_selected"


def make_readme(run_dir: Path, bundle_dir: Path, manifest: dict) -> None:
    lines = [
        f"# Compact intelligence run artifact: {run_dir.name}",
        "",
        "This bundle was produced by `scripts/compact_intelligence_run.py`.",
        "",
        "It is intended to preserve the reproducible high-value parts of a run without keeping bulky local intermediates.",
        "",
        "## Contents",
        "",
        "- ranked Monte Carlo/training summaries when available",
        "- stress/training manifests and status files",
        "- selected top prediction parquet files",
        "- compact validation summaries",
        "- log tails rather than full logs",
        "",
        "## Manifest summary",
        "",
        f"- source_run_dir: `{manifest.get('source_run_dir')}`",
        f"- created_at_utc: `{manifest.get('created_at_utc')}`",
        f"- copied_files: `{len(manifest.get('files', []))}`",
        f"- copied_size: `{human_size(int(manifest.get('copied_size_bytes', 0)))}`",
        f"- skipped_files: `{len(manifest.get('skipped_files', []))}`",
        "",
    ]
    (bundle_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def make_archive(bundle_dir: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.suffixes[-2:] == [".tar", ".gz"] or archive_path.name.endswith(".tgz"):
        mode = "w:gz"
    else:
        if not archive_path.name.endswith(".tar.gz"):
            archive_path = archive_path.with_suffix(archive_path.suffix + ".tar.gz") if archive_path.suffix else archive_path.with_suffix(".tar.gz")
        mode = "w:gz"
    with tarfile.open(archive_path, mode) as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    return archive_path


def delete_heavy(run_dir: Path, yes: bool) -> None:
    targets = []
    for p in run_dir.rglob("*"):
        if p.is_file() and match_any(p.name, HEAVY_PATTERNS):
            targets.append(p)
    print(f"Heavy local delete candidates: {len(targets):,}")
    for p in sorted(targets, key=lambda x: x.stat().st_size if x.exists() else 0, reverse=True)[:50]:
        try:
            print(f"candidate {human_size(p.stat().st_size):>10s} {p}")
        except OSError:
            pass
    if not yes:
        print("Refusing to delete without --yes.")
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
    ap.add_argument("--run-dir", required=True, help="Finished intelligence run directory")
    ap.add_argument("--artifact-root", default="outputs/compact_artifacts", help="Where compact bundle folder/tarball is created")
    ap.add_argument("--top-configs", type=int, default=10, help="Number of unique top configs whose prediction parquet files are copied")
    ap.add_argument("--include-plots", action="store_true", help="Include PNG/HTML plots/reports")
    ap.add_argument("--include-raw", action="store_true", help="Include raw JSONL files. Default false.")
    ap.add_argument("--log-tail-bytes", type=int, default=500_000, help="Bytes to keep from each log file")
    ap.add_argument("--archive", action="store_true", help="Create .tar.gz archive from compact bundle")
    ap.add_argument("--delete-heavy-local", action="store_true", help="After compacting, delete heavy local candidates from run dir")
    ap.add_argument("--yes", action="store_true", help="Required with --delete-heavy-local")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"run dir does not exist: {run_dir}")

    artifact_root = Path(args.artifact_root).resolve()
    bundle_dir = artifact_root / run_dir.name
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    ranked = run_dir / "all_monte_carlo_ranked.csv"
    top_configs = set(read_top_configs(ranked, args.top_configs))

    manifest: dict = {
        "version": "v5.9",
        "source_run_dir": str(run_dir),
        "bundle_dir": str(bundle_dir),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "top_configs": sorted(top_configs),
        "files": [],
        "skipped_files": [],
        "copied_size_bytes": 0,
    }

    for src in sorted(run_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(run_dir)
        keep, reason = should_keep_file(src, run_dir, top_configs, args.include_plots, args.include_raw)
        if not keep:
            manifest["skipped_files"].append({"path": str(rel), "reason": reason, "size_bytes": src.stat().st_size})
            continue
        dst = bundle_dir / rel
        if reason == "log_tail":
            copy_log_tail(src, dst, args.log_tail_bytes)
        else:
            safe_copy(src, dst)
        try:
            size = dst.stat().st_size
            digest = sha256_file(dst)
        except OSError:
            size = 0
            digest = ""
        manifest["files"].append({"path": str(rel), "reason": reason, "size_bytes": size, "sha256": digest})
        manifest["copied_size_bytes"] += size

    make_readme(run_dir, bundle_dir, manifest)
    manifest["files"].append({"path": "README.md", "reason": "generated_readme", "size_bytes": (bundle_dir / "README.md").stat().st_size, "sha256": sha256_file(bundle_dir / "README.md")})
    (bundle_dir / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Compact bundle: {bundle_dir}")
    print(f"Copied files: {len(manifest['files']):,}")
    print(f"Copied size: {human_size(int(manifest['copied_size_bytes']))}")
    print(f"Skipped files: {len(manifest['skipped_files']):,}")
    print(f"Top configs kept: {len(top_configs):,}")

    if args.archive:
        archive_path = make_archive(bundle_dir, artifact_root / f"{run_dir.name}.tar.gz")
        print(f"Archive: {archive_path} ({human_size(archive_path.stat().st_size)})")

    if args.delete_heavy_local:
        delete_heavy(run_dir, args.yes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
