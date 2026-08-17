"""Offline contract tests for the shared table-I/O utility."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


try:
    import pandas as pd
except ImportError:  # pragma: no cover - exercised by dependency-light CI
    pd = None


@unittest.skipIf(pd is None, "pandas is not installed in the current environment")
class TableIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backtester.utils.tables import read_table, write_table

        cls.read_table = staticmethod(read_table)
        cls.write_table = staticmethod(write_table)

    def test_csv_round_trip_preserves_columns_values_and_excludes_index(self):
        frame = pd.DataFrame({"date": ["2026-01-02", "2026-01-03"], "value": [1.25, -2.5]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "table.csv"
            self.write_table(frame, path)
            result = self.read_table(path)
        self.assertEqual(list(result.columns), ["date", "value"])
        self.assertEqual(result.to_dict("records"), frame.to_dict("records"))

    def test_parquet_round_trip_when_engine_is_available(self):
        frame = pd.DataFrame({"ticker": ["AAA", "BBB"], "score": [1.0, 2.0]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.pq"
            try:
                self.write_table(frame, path)
                result = self.read_table(path)
            except (ImportError, ModuleNotFoundError, ValueError) as exc:
                self.skipTest(f"local Parquet engine unavailable: {exc}")
        self.assertEqual(list(result.columns), ["ticker", "score"])
        self.assertEqual(result.to_dict("records"), frame.to_dict("records"))

    def test_unsupported_extension_fails_without_creating_parent(self):
        frame = pd.DataFrame({"value": [1]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not_created" / "table.json"
            with self.assertRaisesRegex(ValueError, "Unsupported table type"):
                self.write_table(frame, path)
            self.assertFalse(path.parent.exists())

    def test_legacy_candidates_import_path_is_compatible(self):
        from backtester.intelligence.candidates import read_table as legacy_read
        from backtester.intelligence.candidates import write_table as legacy_write

        self.assertIs(legacy_read, self.read_table)
        self.assertIs(legacy_write, self.write_table)


if __name__ == "__main__":
    unittest.main()
