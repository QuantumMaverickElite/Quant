#!/usr/bin/env python3
"""Copy compact artifact bundles into a private artifact Git repo and optionally commit.

This is intentionally simple and conservative. It never deletes source files and it does
not push unless --push is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path, dry_run: bool) -> int:
    print("$ " + " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd, cwd=str(cwd))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", required=True, help="File or folder produced by compact_intelligence_run.py")
    ap.add_argument("--artifact-repo", required=True, help="Local path to private artifact repo")
    ap.add_argument("--subdir", default="intelligence_runs", help="Subdirectory inside artifact repo")
    ap.add_argument("--message", help="Commit message")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.artifact).resolve()
    repo = Path(args.artifact_repo).resolve()
    if not src.exists():
        raise SystemExit(f"artifact does not exist: {src}")
    if not repo.exists():
        raise SystemExit(f"artifact repo does not exist: {repo}")
    if not (repo / ".git").exists():
        raise SystemExit(f"not a git repo: {repo}")

    dest_dir = repo / args.subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    if src.is_dir():
        if dest.exists() and not args.dry_run:
            shutil.rmtree(dest)
        print(f"copydir {src} -> {dest}")
        if not args.dry_run:
            shutil.copytree(src, dest)
    else:
        print(f"copy {src} -> {dest}")
        if not args.dry_run:
            shutil.copy2(src, dest)

    meta = {
        "source": str(src),
        "dest": str(dest),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "is_dir": src.is_dir(),
    }
    if src.is_file() and not args.dry_run:
        meta["size_bytes"] = src.stat().st_size
        meta["sha256"] = sha256_file(src)
    meta_path = dest_dir / f"{src.name}.archive_manifest.json"
    print(f"write {meta_path}")
    if not args.dry_run:
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

    if args.commit or args.push:
        run(["git", "add", str(dest.relative_to(repo)), str(meta_path.relative_to(repo))], repo, args.dry_run)
        msg = args.message or f"Archive compact quant artifact {src.name}"
        rc = run(["git", "commit", "-m", msg], repo, args.dry_run)
        if rc != 0:
            print("git commit returned non-zero. This may mean there were no changes.")
        if args.push:
            run(["git", "push"], repo, args.dry_run)
    else:
        print("Copied only. Use --commit and optionally --push to update remote.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
