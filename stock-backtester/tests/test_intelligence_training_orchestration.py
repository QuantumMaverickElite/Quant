import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backtester.intelligence.training_orchestration import (
    path_for_float,
    quote_cmd,
    require_paths,
    run_step,
)


try:
    TEMP_FIXTURES_AVAILABLE = os.access(tempfile.gettempdir(), os.W_OK)
except FileNotFoundError:
    TEMP_FIXTURES_AVAILABLE = False


class TrainingOrchestrationTests(unittest.TestCase):
    def test_path_and_command_formatting(self):
        self.assertEqual(path_for_float(-1.25), "m1p25")
        self.assertEqual(quote_cmd(["python", "a file.py", "--x", "1"]), "python 'a file.py' --x 1")

    @unittest.skipUnless(TEMP_FIXTURES_AVAILABLE, "managed checkout has no writable temporary directory")
    def test_require_paths_preserves_existing_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            present = root / "present.txt"
            present.write_text("ok", encoding="utf-8")
            self.assertEqual(require_paths([str(present), str(root / "missing")], label="inputs"), [present])

    @mock.patch("backtester.intelligence.training_orchestration.subprocess.run")
    @unittest.skipUnless(TEMP_FIXTURES_AVAILABLE, "managed checkout has no writable temporary directory")
    def test_run_step_records_manifest_and_command(self, run):
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "run" / "manifest.csv"
            rows = []
            run_step("demo", ["python", "-m", "demo"], manifest=manifest, rows=rows, keep_going=False)
            run.assert_called_once_with(["python", "-m", "demo"], text=True)
            with manifest.open(newline="", encoding="utf-8") as f:
                record = next(csv.DictReader(f))
            self.assertEqual(record["step"], "demo")
            self.assertEqual(record["returncode"], "0")
            self.assertEqual(record["command"], "python -m demo")

    @mock.patch("backtester.intelligence.training_orchestration.subprocess.run")
    @unittest.skipUnless(TEMP_FIXTURES_AVAILABLE, "managed checkout has no writable temporary directory")
    def test_run_step_fail_fast_and_keep_going(self, run):
        run.return_value.returncode = 3
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.csv"
            with self.assertRaises(SystemExit) as raised:
                run_step("fail", ["child"], manifest=manifest, rows=[], keep_going=False)
            self.assertEqual(raised.exception.code, 3)
            run_step("continue", ["child"], manifest=manifest, rows=[], keep_going=True)


if __name__ == "__main__":
    unittest.main()
