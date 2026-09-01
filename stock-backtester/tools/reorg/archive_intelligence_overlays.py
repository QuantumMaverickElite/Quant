#!/usr/bin/env python3
"""Copy and verify Phase 25 intelligence overlays in a tracked archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


EXPECTED_ROWS = 289
EXPECTED_OVERLAYS = 66
EXPECTED_AGGREGATE = "7225c8d7e31925e09ee00737d3e2becde81b09425a9e3d2cfb3ce74182278c47"
REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "stock-backtester/docs/reorg/PHASE25_OVERLAY_PRESERVATION.csv"
VERIFICATION = REPO_ROOT / "stock-backtester/docs/reorg/PHASE25B_OVERLAY_ARCHIVE_VERIFICATION.csv"
ARCHIVE_ROOT = REPO_ROOT / "archive/intelligence_overlays"


@dataclass(frozen=True)
class PreservationRow:
    overlay_path: str
    file_path: str
    size_bytes: int
    sha256: str
    relationship: str

    @property
    def source(self) -> Path:
        return REPO_ROOT / self.overlay_path / self.file_path

    @property
    def origin_lane(self) -> str:
        if self.overlay_path.startswith("stock-backtester/"):
            return "stock_backtester_root"
        return "repository_root"

    @property
    def archived_overlay_path(self) -> Path:
        return Path(self.origin_lane) / Path(self.overlay_path).name

    @property
    def archived(self) -> Path:
        return ARCHIVE_ROOT / self.archived_overlay_path / self.file_path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows() -> list[PreservationRow]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.DictReader(handle))
    rows = [
        PreservationRow(
            overlay_path=row["overlay_path"],
            file_path=row["file_path"],
            size_bytes=int(row["size_bytes"]),
            sha256=row["sha256"],
            relationship=row["relationship"],
        )
        for row in raw_rows
    ]
    overlays = {row.overlay_path for row in rows}
    if len(rows) != EXPECTED_ROWS or len(overlays) != EXPECTED_OVERLAYS:
        raise RuntimeError(
            f"Unexpected manifest shape: rows={len(rows)} overlays={len(overlays)}"
        )
    return rows


def verify_file(path: Path, row: PreservationRow) -> str | None:
    if not path.is_file():
        return f"missing: {path}"
    actual_size = path.stat().st_size
    if actual_size != row.size_bytes:
        return f"size mismatch: {path}: {actual_size} != {row.size_bytes}"
    actual_hash = file_sha256(path)
    if actual_hash != row.sha256:
        return f"hash mismatch: {path}: {actual_hash} != {row.sha256}"
    return None


def aggregate_for(rows: list[PreservationRow], archived: bool) -> str:
    lines = []
    for row in rows:
        path = row.archived if archived else row.source
        # Preserve the original path identity so source and archive aggregates
        # are comparable even though the archive has two provenance lanes.
        original = Path(row.overlay_path) / row.file_path
        lines.append((str(original), f"{file_sha256(path)}  {original}\n"))
    payload = "".join(value for _, value in sorted(lines)).encode()
    return hashlib.sha256(payload).hexdigest()


def meaningful_source_files(rows: list[PreservationRow]) -> set[Path]:
    files: set[Path] = set()
    for overlay in sorted({REPO_ROOT / row.overlay_path for row in rows}):
        for path in overlay.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            files.add(path)
    return files


def expected_source_files(rows: list[PreservationRow]) -> set[Path]:
    return {row.source for row in rows}


def expected_archive_files(rows: list[PreservationRow]) -> set[Path]:
    return {row.archived for row in rows}


def actual_archive_files() -> set[Path]:
    files: set[Path] = set()
    for lane in ("repository_root", "stock_backtester_root"):
        root = ARCHIVE_ROOT / lane
        if root.exists():
            files.update(path for path in root.rglob("*") if path.is_file())
    return files


def verify_sources(rows: list[PreservationRow]) -> None:
    errors = [error for row in rows if (error := verify_file(row.source, row))]
    expected = expected_source_files(rows)
    actual = meaningful_source_files(rows)
    if actual != expected:
        errors.append(
            f"source file-set mismatch: missing={len(expected - actual)} extra={len(actual - expected)}"
        )
    if not errors:
        aggregate = aggregate_for(rows, archived=False)
        if aggregate != EXPECTED_AGGREGATE:
            errors.append(f"source aggregate mismatch: {aggregate}")
    if errors:
        raise RuntimeError("\n".join(errors))
    print(f"source verified: rows={len(rows)} overlays={EXPECTED_OVERLAYS} aggregate={EXPECTED_AGGREGATE}")


def copy_archive(rows: list[PreservationRow]) -> None:
    verify_sources(rows)
    for row in rows:
        row.archived.parent.mkdir(parents=True, exist_ok=True)
        if row.archived.exists() and verify_file(row.archived, row) is not None:
            raise RuntimeError(f"Refusing to overwrite differing archive file: {row.archived}")
        shutil.copy2(row.source, row.archived)
    verify_archive(rows, write_manifest=True)


def write_verification(rows: list[PreservationRow]) -> None:
    fields = [
        "original_overlay_path",
        "archived_overlay_path",
        "relative_file_path",
        "size_bytes",
        "sha256",
        "phase25_relationship",
        "source_verified",
        "archive_verified",
    ]
    with VERIFICATION.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "original_overlay_path": row.overlay_path,
                    "archived_overlay_path": str(row.archived_overlay_path),
                    "relative_file_path": row.file_path,
                    "size_bytes": row.size_bytes,
                    "sha256": row.sha256,
                    "phase25_relationship": row.relationship,
                    "source_verified": "yes",
                    "archive_verified": "yes",
                }
            )


def verify_archive(rows: list[PreservationRow], write_manifest: bool = False) -> None:
    verify_sources(rows)
    errors = [error for row in rows if (error := verify_file(row.archived, row))]
    expected = expected_archive_files(rows)
    actual = actual_archive_files()
    if actual != expected:
        errors.append(
            f"archive file-set mismatch: missing={len(expected - actual)} extra={len(actual - expected)}"
        )
    if not errors:
        aggregate = aggregate_for(rows, archived=True)
        if aggregate != EXPECTED_AGGREGATE:
            errors.append(f"archive aggregate mismatch: {aggregate}")
    if errors:
        raise RuntimeError("\n".join(errors))
    missing_doc = (
        ARCHIVE_ROOT
        / "stock_backtester_root/market_intelligence_v2_6_2_overlay/docs/market_intelligence_v2_6_2.md"
    )
    expected_missing_hash = "37b9dc082c673ca814792f2fb17eb71faf9f3173d47ec6581464f0ff91fbaf58"
    if file_sha256(missing_doc) != expected_missing_hash:
        raise RuntimeError("Canonical-missing v2.6.2 document failed verification")
    if write_manifest:
        write_verification(rows)
    print(f"archive verified: rows={len(rows)} overlays={EXPECTED_OVERLAYS} aggregate={EXPECTED_AGGREGATE}")


def remove_sources(rows: list[PreservationRow], confirmed: bool) -> None:
    if not confirmed:
        raise RuntimeError("Removal requires --confirm-remove-verified-sources")
    verify_archive(rows, write_manifest=True)
    overlays = sorted({REPO_ROOT / row.overlay_path for row in rows})
    for overlay in overlays:
        if not overlay.name.startswith("market_intelligence_") or not overlay.name.endswith("_overlay"):
            raise RuntimeError(f"Refusing unexpected removal target: {overlay}")
        if overlay.parent not in {REPO_ROOT, REPO_ROOT / "stock-backtester"}:
            raise RuntimeError(f"Refusing target outside audited roots: {overlay}")
    for overlay in overlays:
        shutil.rmtree(overlay)
    remaining = [str(path) for path in overlays if path.exists()]
    if remaining:
        raise RuntimeError("Overlay removal incomplete:\n" + "\n".join(remaining))
    verify_archive(rows, write_manifest=True)
    print(f"removed verified sources: overlays={len(overlays)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy, verify, or remove Phase 25 intelligence overlays."
    )
    parser.add_argument("action", choices=("verify-sources", "copy", "verify", "remove-sources"))
    parser.add_argument("--confirm-remove-verified-sources", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_rows()
    if args.action == "verify-sources":
        verify_sources(rows)
    elif args.action == "copy":
        copy_archive(rows)
    elif args.action == "verify":
        verify_archive(rows, write_manifest=True)
    else:
        remove_sources(rows, args.confirm_remove_verified_sources)


if __name__ == "__main__":
    main()
