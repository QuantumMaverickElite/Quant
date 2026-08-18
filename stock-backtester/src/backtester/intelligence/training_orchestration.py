"""Shared mechanics for historical intelligence-training command wrappers.

The command scripts retain their own research policy and argument defaults.
This module centralizes only manifest writing, child-step launching, and small
command/path formatting helpers that are shared by multiple runners.
"""

from __future__ import annotations

import csv
import shlex
import subprocess
import time
from pathlib import Path


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["step", "returncode", "elapsed_seconds", "command"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_step(name: str, cmd: list[str], *, manifest: Path, rows: list[dict], keep_going: bool) -> None:
    """Run one child command using the historical manifest/fail-fast contract."""
    print("\n" + "=" * 80)
    print(name)
    print(" ".join(cmd))
    started = time.time()
    completed = subprocess.run(cmd, text=True)
    elapsed = time.time() - started
    rows.append(
        {
            "step": name,
            "returncode": completed.returncode,
            "elapsed_seconds": round(elapsed, 3),
            "command": " ".join(cmd),
        }
    )
    write_manifest(manifest, rows)
    if completed.returncode != 0 and not keep_going:
        raise SystemExit(completed.returncode)


def path_for_float(value: float) -> str:
    return str(value).replace(".", "p").replace("-", "m")


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
