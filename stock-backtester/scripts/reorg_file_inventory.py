#!/usr/bin/env python3
"""Classify repo files before moving anything.

This audit is intentionally conservative. It does not modify files.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


def load_policy(root: Path) -> dict[str, Any]:
    p = root / "configs" / "reorg_audit_policy.json"
    if p.exists():
        return json.loads(p.read_text())
    return {
        "ignore_dirs": [".git", ".venv", "__pycache__", "outputs", "data", "target"],
        "generated_extensions": [".csv", ".json", ".jsonl", ".parquet", ".png", ".mp4", ".npy", ".npz", ".bin"],
        "code_extensions": [".py", ".rs", ".sh", ".toml"],
        "doc_extensions": [".md", ".rst", ".txt"],
        "overlay_dir_pattern": "market_intelligence_*_overlay",
        "active_package_prefix": "src/backtester",
        "script_dir": "scripts",
    }


def is_ignored(rel: PurePosixPath, ignore_dirs: set[str]) -> bool:
    return any(part in ignore_dirs for part in rel.parts)


def classify(rel: PurePosixPath, policy: dict[str, Any]) -> str:
    parts = rel.parts
    suffix = rel.suffix.lower()
    generated = set(policy.get("generated_extensions", []))
    code = set(policy.get("code_extensions", []))
    docs = set(policy.get("doc_extensions", []))

    if any(part.startswith("market_intelligence_") and part.endswith("_overlay") for part in parts):
        if suffix in code:
            return "overlay_code"
        if suffix in docs:
            return "overlay_doc"
        if suffix in generated:
            return "overlay_artifact"
        return "overlay_other"
    if parts and parts[0] == "archive":
        return "archive"
    if parts and parts[0] == "assets":
        return "asset"
    if parts and parts[0] == "docs":
        return "doc"
    if str(rel).startswith(str(policy.get("active_package_prefix", "src/backtester"))):
        return "active_package_code" if suffix in code else "active_package_other"
    if parts and parts[0] == policy.get("script_dir", "scripts"):
        return "script_code" if suffix in code else "script_other"
    if suffix in generated:
        return "generated_artifact"
    if suffix in code:
        return "other_code"
    if suffix in docs:
        return "other_doc"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify files for safe repo reorganization.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="outputs/reorg_audit/latest")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    policy = load_policy(root)
    ignore_dirs = set(policy.get("ignore_dirs", []))

    rows: list[dict[str, str | int]] = []
    counts: Counter[str] = Counter()
    bytes_by_class: Counter[str] = Counter()
    ext_counts: Counter[str] = Counter()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if is_ignored(rel, ignore_dirs):
            continue
        cls = classify(rel, policy)
        size = path.stat().st_size
        rows.append({"path": rel.as_posix(), "class": cls, "suffix": rel.suffix.lower(), "bytes": size})
        counts[cls] += 1
        bytes_by_class[cls] += size
        ext_counts[rel.suffix.lower() or "<none>"] += 1

    csv_path = out / "reorg_file_inventory.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "class", "suffix", "bytes"])
        writer.writeheader()
        writer.writerows(rows)

    md = ["# File Inventory Audit", "", f"Root: `{root}`", "", "## Counts by class", ""]
    for cls, n in counts.most_common():
        md.append(f"- `{cls}`: {n} files, {bytes_by_class[cls]:,} bytes")
    md += ["", "## Top extensions", ""]
    for ext, n in ext_counts.most_common(30):
        md.append(f"- `{ext}`: {n}")
    md += ["", "## Suggested first cleanup targets", ""]
    for target in ["overlay_code", "overlay_doc", "overlay_artifact", "archive", "asset", "generated_artifact"]:
        if counts[target]:
            md.append(f"- `{target}`: review/archive policy before active refactor")
    (out / "reorg_file_inventory.md").write_text("\n".join(md) + "\n")

    payload = {
        "root": str(root),
        "counts_by_class": dict(counts),
        "bytes_by_class": dict(bytes_by_class),
        "extension_counts": dict(ext_counts),
        "csv": str(csv_path),
    }
    (out / "reorg_file_inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {csv_path}")
    print(f"Wrote {out / 'reorg_file_inventory.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
