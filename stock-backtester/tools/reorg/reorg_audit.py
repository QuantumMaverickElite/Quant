#!/usr/bin/env python3
"""Audit repository structure before the stock-backtester reorganization.

This script is intentionally dependency-free. It writes JSON and Markdown reports
that make it easier to decide what to move, archive, wrap, or protect.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".vnev",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "outputs",
    "data",
    "target",
    "node_modules",
}

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".csv",
    ".rs",
    ".sh",
}


@dataclass
class PythonFileAudit:
    path: str
    imports: list[str]
    internal_imports: list[str]
    has_main_guard: bool
    line_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory.")
    parser.add_argument("--out", default="outputs/reorg_audit/latest", help="Output directory.")
    parser.add_argument(
        "--include-overlays",
        action="store_true",
        help="Include market_intelligence_*_overlay directories in detailed import parsing.",
    )
    return parser.parse_args()


def should_skip_dir(path: Path, include_overlays: bool) -> bool:
    name = path.name
    if name in DEFAULT_EXCLUDE_DIRS:
        return True
    if not include_overlays and name.startswith("market_intelligence_") and name.endswith("_overlay"):
        return True
    return False


def iter_files(root: Path, include_overlays: bool) -> list[Path]:
    files: list[Path] = []
    for current, dirs, filenames in os.walk(root):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if not should_skip_dir(current_path / d, include_overlays)]
        for filename in filenames:
            files.append(current_path / filename)
    return sorted(files)


def line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def import_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return None
    if isinstance(node, ast.ImportFrom):
        return node.module
    return None


def audit_python_file(path: Path, root: Path) -> PythonFileAudit:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="ignore")
    imports: list[str] = []
    internal: list[str] = []
    has_main_guard = "__main__" in text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return PythonFileAudit(rel, [], [], has_main_guard, text.count("\n") + 1)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    imports = sorted(set(imports))
    internal = sorted({m for m in imports if m.startswith("backtester") or m.startswith("scripts")})
    return PythonFileAudit(rel, imports, internal, has_main_guard, text.count("\n") + 1)


def short_hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:16]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    files_no_overlays = iter_files(root, include_overlays=False)
    files_with_overlays = iter_files(root, include_overlays=True)
    detail_files = files_with_overlays if args.include_overlays else files_no_overlays

    overlay_dirs = sorted(
        p.relative_to(root).as_posix()
        for p in root.iterdir()
        if p.is_dir() and p.name.startswith("market_intelligence_") and p.name.endswith("_overlay")
    )

    ext_counts = Counter(p.suffix.lower() or "<no_ext>" for p in files_with_overlays)
    ext_counts_no_overlays = Counter(p.suffix.lower() or "<no_ext>" for p in files_no_overlays)
    top_dirs = Counter(p.relative_to(root).parts[0] for p in files_with_overlays if p.relative_to(root).parts)

    py_files = [p for p in detail_files if p.suffix == ".py"]
    py_audits = [audit_python_file(p, root) for p in py_files]

    scripts = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "scripts").glob("*.py")
        if p.is_file()
    ) if (root / "scripts").exists() else []

    internal_import_counter: Counter[str] = Counter()
    script_imports: dict[str, list[str]] = {}
    for audit in py_audits:
        for imp in audit.internal_imports:
            internal_import_counter[imp] += 1
        if audit.path.startswith("scripts/"):
            script_imports[audit.path] = audit.internal_imports

    basename_groups: dict[str, list[str]] = defaultdict(list)
    for p in files_with_overlays:
        basename_groups[p.name].append(p.relative_to(root).as_posix())
    duplicate_basenames = {
        name: paths for name, paths in basename_groups.items()
        if len(paths) >= 3 and (name.endswith(".py") or name.endswith(".md"))
    }

    large_text_files: list[dict[str, Any]] = []
    for p in files_with_overlays:
        if p.suffix.lower() in TEXT_EXTENSIONS:
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size >= 250_000:
                large_text_files.append({
                    "path": p.relative_to(root).as_posix(),
                    "bytes": size,
                    "sha256_16": short_hash(p),
                })
    large_text_files.sort(key=lambda x: x["bytes"], reverse=True)

    report = {
        "root": str(root),
        "file_count_with_overlays": len(files_with_overlays),
        "file_count_without_overlays": len(files_no_overlays),
        "overlay_dir_count": len(overlay_dirs),
        "overlay_dirs": overlay_dirs,
        "extension_counts_with_overlays": dict(ext_counts.most_common()),
        "extension_counts_without_overlays": dict(ext_counts_no_overlays.most_common()),
        "top_level_file_counts": dict(top_dirs.most_common()),
        "top_internal_imports": dict(internal_import_counter.most_common(50)),
        "script_count": len(scripts),
        "scripts": scripts,
        "script_internal_imports": script_imports,
        "python_files": [asdict(a) for a in py_audits],
        "duplicate_basenames": duplicate_basenames,
        "large_text_files": large_text_files[:100],
    }

    (out / "reorg_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True))

    md_lines = [
        "# Reorganization Audit",
        "",
        f"Root: `{root}`",
        "",
        "## Counts",
        "",
        f"- Files with overlays: {len(files_with_overlays)}",
        f"- Files without overlays: {len(files_no_overlays)}",
        f"- Overlay directories: {len(overlay_dirs)}",
        f"- Top-level scripts: {len(scripts)}",
        "",
        "## Top-level file counts",
        "",
    ]
    for name, count in top_dirs.most_common(25):
        md_lines.append(f"- `{name}`: {count}")
    md_lines.extend(["", "## Top internal imports", ""])
    for name, count in internal_import_counter.most_common(25):
        md_lines.append(f"- `{name}`: {count}")
    md_lines.extend(["", "## Large generated-looking text files", ""])
    for item in large_text_files[:25]:
        md_lines.append(f"- `{item['path']}` — {item['bytes']:,} bytes — {item['sha256_16']}")
    md_lines.extend(["", "## Duplicate Python/Markdown basenames", ""])
    for name, paths in sorted(duplicate_basenames.items())[:50]:
        md_lines.append(f"- `{name}` appears {len(paths)} times")
    md_lines.append("")

    (out / "reorg_audit.md").write_text("\n".join(md_lines))
    print(f"Wrote {out / 'reorg_audit.json'}")
    print(f"Wrote {out / 'reorg_audit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
