#!/usr/bin/env python3
"""Small offline tests for the Phase 0 inventory helper."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "reorg" / "reorg_phase0_inventory.py"
SPEC = importlib.util.spec_from_file_location("reorg_phase0_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Phase0InventoryTests(unittest.TestCase):
    def test_script_roles_use_structural_evidence(self) -> None:
        role, confidence, _ = MODULE.classify_script(
            "scripts/workers/run_source_fetch_worker.sh",
            "PYTHONPATH=src python scripts/fetch_historical_news_sources.py",
            ["scripts/fetch_historical_news_sources.py"],
            False,
        )
        self.assertEqual(role, "WORKER / REMOTE TOOLING")
        self.assertEqual(confidence, "HIGH")

    def test_overlay_relationships_and_missing_destination(self) -> None:
        with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
            repo = Path(tmp)
            project = repo / "stock-backtester"
            (project / "docs").mkdir(parents=True)
            overlay = project / "market_intelligence_v2_6_2_overlay" / "docs"
            overlay.mkdir(parents=True)
            (project / "docs" / "same.md").write_text("same\n")
            (overlay / "same.md").write_text("same\n")
            (overlay / "missing.md").write_text("missing\n")
            rows = MODULE.build_overlay_rows(project, repo, {"docs/same.md"})
            by_file = {row["file_path"]: row for row in rows}
            self.assertEqual(by_file["docs/same.md"]["relationship"], "IDENTICAL")
            self.assertEqual(by_file["docs/missing.md"]["relationship"], "CANONICAL MISSING")

    def test_output_contracts_are_stably_ordered(self) -> None:
        with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            paths = ["scripts/a.py", "scripts/b.py"]
            (root / paths[0]).write_text("x='outputs/signals/a.parquet'\n")
            (root / paths[1]).write_text("x='outputs/signals/a.parquet'\n")
            first = MODULE.build_contract_rows(root, paths)
            second = MODULE.build_contract_rows(root, list(reversed(paths)))
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
