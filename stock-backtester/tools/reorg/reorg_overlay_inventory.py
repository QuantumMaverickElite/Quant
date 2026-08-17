#!/usr/bin/env python3
"""Inventory market_intelligence overlay directories.

This is a read-only audit that helps decide what to archive, promote, or delete.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def sha16(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def load_policy(root: Path) -> dict[str, Any]:
    p = root / "configs" / "reorg_audit_policy.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"ignore_dirs": [".git", ".venv", "__pycache__", "outputs", "data", "target"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventory overlay directories before reorg.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="outputs/reorg_audit/latest")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    policy = load_policy(root)
    ignore_dirs = set(policy.get("ignore_dirs", []))

    overlays = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("market_intelligence_") and p.name.endswith("_overlay")])

    rows: list[dict[str, str | int]] = []
    hash_to_paths: defaultdict[str, list[str]] = defaultdict(list)
    basename_to_paths: defaultdict[str, list[str]] = defaultdict(list)
    suffix_counts: Counter[str] = Counter()
    files_by_overlay: Counter[str] = Counter()
    bytes_by_overlay: Counter[str] = Counter()

    for overlay in overlays:
        for path in sorted(overlay.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if any(part in ignore_dirs for part in Path(rel).parts):
                continue
            size = path.stat().st_size
            digest = sha16(path)
            rows.append({
                "overlay": overlay.name,
                "path": rel,
                "relative_inside_overlay": path.relative_to(overlay).as_posix(),
                "basename": path.name,
                "suffix": path.suffix.lower(),
                "bytes": size,
                "sha16": digest,
            })
            hash_to_paths[digest].append(rel)
            basename_to_paths[path.name].append(rel)
            suffix_counts[path.suffix.lower() or "<none>"] += 1
            files_by_overlay[overlay.name] += 1
            bytes_by_overlay[overlay.name] += size

    csv_path = out / "reorg_overlay_inventory.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["overlay", "path", "relative_inside_overlay", "basename", "suffix", "bytes", "sha16"])
        writer.writeheader()
        writer.writerows(rows)

    duplicate_hashes = {h: ps for h, ps in hash_to_paths.items() if len(ps) > 1}
    duplicate_basenames = {b: ps for b, ps in basename_to_paths.items() if len(ps) > 1}

    md = ["# Overlay Inventory Audit", "", f"Root: `{root}`", "", f"Overlay directories: {len(overlays)}", f"Overlay files: {len(rows)}", ""]
    md += ["## Files by overlay", ""]
    for name, n in files_by_overlay.most_common():
        md.append(f"- `{name}`: {n} files, {bytes_by_overlay[name]:,} bytes")
    md += ["", "## Extension counts", ""]
    for ext, n in suffix_counts.most_common():
        md.append(f"- `{ext}`: {n}")
    md += ["", "## Exact duplicate content hashes", ""]
    for h, ps in sorted(duplicate_hashes.items(), key=lambda kv: len(kv[1]), reverse=True)[:50]:
        md.append(f"- `{h}`: {len(ps)} files")
        for p in ps[:8]:
            md.append(f"  - `{p}`")
        if len(ps) > 8:
            md.append(f"  - ... {len(ps) - 8} more")
    md += ["", "## Duplicate basenames", ""]
    for b, ps in sorted(duplicate_basenames.items(), key=lambda kv: len(kv[1]), reverse=True)[:75]:
        md.append(f"- `{b}`: {len(ps)} files")
    (out / "reorg_overlay_inventory.md").write_text("\n".join(md) + "\n")

    payload = {
        "root": str(root),
        "overlay_count": len(overlays),
        "overlay_files": len(rows),
        "files_by_overlay": dict(files_by_overlay),
        "bytes_by_overlay": dict(bytes_by_overlay),
        "suffix_counts": dict(suffix_counts),
        "duplicate_hashes": duplicate_hashes,
        "duplicate_basenames": duplicate_basenames,
        "csv": str(csv_path),
    }
    (out / "reorg_overlay_inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {csv_path}")
    print(f"Wrote {out / 'reorg_overlay_inventory.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
