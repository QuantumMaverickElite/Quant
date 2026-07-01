#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import shutil

ROOT = Path("outputs/intelligence/training_runs")

KEEP_DIR_NAMES = {
    "ml_policy_candidate_validation",
    "ml_policy_candidate_validation_multi",
}

LARGE_EXTS = {".jsonl", ".log"}


def human(n: int) -> str:
    units = ["B", "K", "M", "G", "T"]
    x = float(n)
    for u in units:
        if x < 1024:
            return f"{x:.1f}{u}"
        x /= 1024
    return f"{x:.1f}P"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Actually delete selected files.")
    p.add_argument("--min-mb", type=float, default=25.0, help="Only target files at least this large.")
    p.add_argument(
        "--target",
        default=str(ROOT),
        help="Training runs root.",
    )
    args = p.parse_args()

    root = Path(args.target)
    if not root.exists():
        raise SystemExit(f"missing: {root}")

    min_bytes = int(args.min_mb * 1024 * 1024)
    candidates = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in KEEP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix not in LARGE_EXTS:
            continue
        size = path.stat().st_size
        if size >= min_bytes:
            candidates.append((size, path))

    candidates.sort(reverse=True)

    total = sum(size for size, _ in candidates)

    print("== intelligence training run prune ==")
    print(f"mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"target: {root}")
    print(f"candidate files: {len(candidates)}")
    print(f"candidate bytes: {human(total)}")
    print()

    for size, path in candidates[:80]:
        print(f"{human(size):>8}  {path}")

    if not args.apply:
        print()
        print("Dry run only. Re-run with --apply to delete these files.")
        return

    for size, path in candidates:
        path.unlink()

    print()
    print(f"Deleted {len(candidates)} files, approx {human(total)}.")

    # Remove empty dirs after deleting files.
    for d in sorted(root.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    main()
