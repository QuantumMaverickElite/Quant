#!/usr/bin/env python3
"""Parse Python imports and report internal dependency edges.

This script is diagnostic only. It does not import project modules and does not
execute project code, which makes it safe during a messy refactor.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


def load_policy(root: Path) -> dict[str, Any]:
    p = root / "configs" / "reorg_audit_policy.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"ignore_dirs": [".git", ".venv", "__pycache__", "outputs", "data", "target"]}


def is_ignored(rel: PurePosixPath, ignore_dirs: set[str]) -> bool:
    return any(part in ignore_dirs for part in rel.parts)


def module_name_for_file(rel: PurePosixPath) -> str:
    parts = list(rel.parts)
    if parts[:1] == ["src"]:
        parts = parts[1:]
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def imports_from_file(path: Path) -> tuple[list[str], str | None]:
    try:
        tree = ast.parse(path.read_text(errors="replace"), filename=str(path))
    except SyntaxError as e:
        return [], f"SyntaxError: {e}"
    except OSError as e:
        return [], f"OSError: {e}"

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
            elif node.level:
                imports.append("." * node.level)
    return imports, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a static internal import graph for reorg planning.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="outputs/reorg_audit/latest")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    policy = load_policy(root)
    ignore_dirs = set(policy.get("ignore_dirs", []))

    py_files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if is_ignored(rel, ignore_dirs):
            continue
        py_files.append(path)

    project_modules: dict[str, str] = {}
    for path in py_files:
        rel = PurePosixPath(path.relative_to(root).as_posix())
        mod = module_name_for_file(rel)
        project_modules[mod] = rel.as_posix()

    edges: list[dict[str, str]] = []
    parse_errors: list[dict[str, str]] = []
    imported_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    script_edges: Counter[str] = Counter()

    for path in py_files:
        rel = PurePosixPath(path.relative_to(root).as_posix())
        source_mod = module_name_for_file(rel)
        imports, err = imports_from_file(path)
        if err:
            parse_errors.append({"path": rel.as_posix(), "error": err})
            continue
        for imp in imports:
            is_internal = imp == "backtester" or imp.startswith("backtester.") or imp.startswith("scripts.")
            if not is_internal:
                continue
            edges.append({"source_path": rel.as_posix(), "source_module": source_mod, "import": imp})
            imported_counter[imp] += 1
            source_counter[source_mod] += 1
            if rel.parts and rel.parts[0] == "scripts":
                script_edges[imp] += 1

    csv_path = out / "reorg_import_edges.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source_path", "source_module", "import"])
        writer.writeheader()
        writer.writerows(edges)

    md = ["# Import Graph Audit", "", f"Root: `{root}`", "", f"Python files parsed: {len(py_files)}", f"Internal import edges: {len(edges)}", ""]
    if parse_errors:
        md += ["## Parse errors", ""]
        for row in parse_errors[:50]:
            md.append(f"- `{row['path']}` — {row['error']}")
        md.append("")
    md += ["## Most imported internal modules", ""]
    for mod, n in imported_counter.most_common(50):
        md.append(f"- `{mod}`: {n}")
    md += ["", "## Internal modules most imported by top-level scripts", ""]
    for mod, n in script_edges.most_common(50):
        md.append(f"- `{mod}`: {n}")
    md += ["", "## Scripts with many internal dependencies", ""]
    for mod, n in source_counter.most_common(50):
        if mod.startswith("scripts."):
            md.append(f"- `{mod}`: {n}")
    (out / "reorg_import_graph.md").write_text("\n".join(md) + "\n")

    payload = {
        "root": str(root),
        "python_files": len(py_files),
        "internal_edges": len(edges),
        "parse_errors": parse_errors,
        "most_imported": imported_counter.most_common(),
        "script_imported": script_edges.most_common(),
        "csv": str(csv_path),
    }
    (out / "reorg_import_graph.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {csv_path}")
    print(f"Wrote {out / 'reorg_import_graph.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
