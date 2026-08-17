"""Offline contract tests for the extracted ML-policy script family."""

from __future__ import annotations

import sys
import importlib.util
from importlib.machinery import ModuleSpec
import subprocess
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


try:
    import numpy as np
    import pandas as pd
except ImportError:  # pragma: no cover - dependency-light environments
    np = None
    pd = None


@unittest.skipIf(pd is None or np is None, "pandas and numpy are required")
class MLPolicyFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backtester.intelligence import ml_policy_application as application
        from backtester.intelligence import ml_policy_permutation as permutation
        from backtester.intelligence import ml_policy_sweep as sweep
        from backtester.intelligence import ml_policy_validation as validation

        cls.application = application
        cls.permutation = permutation
        cls.sweep = sweep
        cls.validation = validation

    @staticmethod
    def load_parent_module(module_name: str, script_path: str):
        repo_root = Path(__file__).resolve().parents[2]
        source = subprocess.check_output(
            ["git", "show", f"678418e:stock-backtester/{script_path}"],
            cwd=repo_root,
            text=True,
        )
        module = importlib.util.module_from_spec(ModuleSpec(module_name, loader=None))
        exec(compile(source, script_path, "exec"), module.__dict__)
        return module

    @staticmethod
    def load_compatibility_script(script_name: str):
        path = Path(__file__).with_name(script_name)
        spec = importlib.util.spec_from_file_location(f"compat_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_policy_application_preserves_schema_and_expected_values(self):
        frame = pd.DataFrame({"baseline": [0.5, 0.5], "ml": [0.51, 0.7], "keep": ["a", "b"]})
        result = self.application.apply_policy(
            frame,
            base_col="baseline",
            ml_col="ml",
            output_col="adjusted",
            strength=20,
            max_abs_delta=0.05,
            min_abs_delta=0.0,
        )
        self.assertEqual(list(result.columns), [
            "baseline", "ml", "keep", "ml_policy_raw_delta", "ml_policy_scaled_delta",
            "ml_policy_capped_delta", "ml_policy_thresholded_delta", "ml_policy_delta_was_capped",
            "ml_policy_delta_was_thresholded", "adjusted",
        ])
        np.testing.assert_allclose(result["adjusted"], [0.55, 0.55])

        parent = self.load_parent_module("parent_application", "scripts/apply_ml_policy_strength.py")
        parent_result = parent.apply_policy(
            frame,
            base_col="baseline",
            ml_col="ml",
            output_col="adjusted",
            strength=20,
            max_abs_delta=0.05,
            min_abs_delta=0.0,
        )
        pd.testing.assert_frame_equal(result, parent_result)

    def test_permutation_policy_and_shuffle_are_seed_deterministic(self):
        frame = pd.DataFrame({"date": ["2026-01-01"] * 3, "base": [0.1, 0.2, 0.3], "ml": [0.3, 0.2, 0.1]})
        first = self.permutation.shuffle_ml_within_date(
            frame, date_col="date", ml_col="ml", rng=np.random.default_rng(42)
        )
        second = self.permutation.shuffle_ml_within_date(
            frame, date_col="date", ml_col="ml", rng=np.random.default_rng(42)
        )
        pd.testing.assert_series_equal(first, second)
        result = self.permutation.policy_confidence(frame["base"], frame["ml"], strength=2, cap=0.1, threshold=0)
        np.testing.assert_allclose(result, [0.2, 0.2, 0.2])
        parent = self.load_parent_module("parent_permutation", "scripts/permutation_test_ml_policy.py")
        parent_result = parent.policy_confidence(frame["base"], frame["ml"], strength=2, cap=0.1, threshold=0)
        pd.testing.assert_series_equal(result, parent_result)
        parent_shuffle = parent.shuffle_ml_within_date(
            frame, date_col="date", ml_col="ml", rng=np.random.default_rng(42)
        )
        pd.testing.assert_series_equal(first, parent_shuffle)

    def test_bootstrap_indices_are_seed_deterministic(self):
        first = self.validation.bootstrap_indices(np.random.default_rng(7), 5, 3, 2)
        second = self.sweep.bootstrap_indices(np.random.default_rng(7), 5, 3, 2)
        np.testing.assert_array_equal(first, second)
        parent_validation = self.load_parent_module("parent_validation", "scripts/validate_ml_policy_candidate.py")
        parent_sweep = self.load_parent_module("parent_sweep", "scripts/sweep_ml_policy_strength.py")
        np.testing.assert_array_equal(
            first, parent_validation.bootstrap_indices(np.random.default_rng(7), 5, 3, 2)
        )
        np.testing.assert_allclose(
            self.sweep.adjusted_confidence(
                pd.Series([0.5, 0.5]), pd.Series([0.51, 0.7]), strength=20, max_abs_delta=0.05, min_abs_delta=0
            ),
            parent_sweep.adjusted_confidence(
                pd.Series([0.5, 0.5]), pd.Series([0.51, 0.7]), strength=20, max_abs_delta=0.05, min_abs_delta=0
            ),
        )

    def test_historical_wrappers_reexport_canonical_symbols(self):
        apply_ml_policy_strength = self.load_compatibility_script("apply_ml_policy_strength.py")
        permutation_test_ml_policy = self.load_compatibility_script("permutation_test_ml_policy.py")
        sweep_ml_policy_strength = self.load_compatibility_script("sweep_ml_policy_strength.py")
        validate_ml_policy_candidate = self.load_compatibility_script("validate_ml_policy_candidate.py")

        self.assertIs(apply_ml_policy_strength.main, self.application.main)
        self.assertIs(permutation_test_ml_policy.main, self.permutation.main)
        self.assertIs(sweep_ml_policy_strength.main, self.sweep.main)
        self.assertIs(validate_ml_policy_candidate.main, self.validation.main)


if __name__ == "__main__":
    unittest.main()
