#!/usr/bin/env python3
"""Run smoke commands for scripts that must survive the reorganization."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="configs/sacred_scripts.json")
    parser.add_argument("--dry-run", action="store_true", help="Print enabled commands without running them.")
    parser.add_argument("--run-disabled", action="store_true", help="Run disabled commands too.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text())
    default_timeout = int(manifest.get("default_timeout_seconds", 120))
    commands = manifest.get("commands", [])

    selected = [cmd for cmd in commands if args.run_disabled or cmd.get("enabled", False)]
    if not selected:
        print("No enabled sacred commands. Edit configs/sacred_scripts.json first, or pass --run-disabled.")
        return 0

    failures: list[str] = []
    for cmd in selected:
        name = cmd.get("name", "<unnamed>")
        command = cmd["command"]
        timeout = int(cmd.get("timeout_seconds", default_timeout))
        print(f"\n==> {name}\n{command}")
        if args.dry_run:
            continue
        result = subprocess.run(command, shell=True, text=True, timeout=timeout)
        if result.returncode != 0:
            failures.append(f"{name} exited with {result.returncode}")

    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("\nAll selected sacred smoke commands passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
