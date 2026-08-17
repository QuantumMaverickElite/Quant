"""Stdlib-only tests for the read-only experiment registry."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backtester import experiments


class ExperimentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = experiments.build_registry()

    def test_registry_valid_and_ids_unique(self):
        self.assertEqual(experiments.validate_registry(self.registry), [])
        ids = [item.id for group in (self.registry.components, self.registry.pipelines, self.registry.experiments, self.registry.commands) for item in group]
        self.assertEqual(len(ids), len(set(ids)))

    def test_json_is_deterministic_and_round_trips(self):
        first = experiments._json(self.registry.to_dict())
        second = experiments._json(experiments.build_registry().to_dict())
        self.assertEqual(first, second)
        self.assertIsInstance(json.loads(first), dict)

    def test_list_and_describe_are_discoverable(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(experiments.main(["list"]), 0)
        self.assertIn("intelligence.ml_policy.permutation", output.getvalue())

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(experiments.main(["describe", "intelligence.ml_policy.permutation"]), 0)
        self.assertIn("HISTORICAL RESEARCH TOOLING", output.getvalue())
        self.assertIn("--seed", output.getvalue())

    def test_json_cli_output_parses(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(experiments.main(["list", "--json"]), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["experiments"][0]["id"], "intelligence.ml_policy.application")

    def test_unknown_experiment_has_nonzero_status(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(experiments.main(["describe", "missing.experiment"]), 2)
        self.assertIn("Unknown experiment ID", errors.getvalue())

    def test_validation_rejects_bad_parameter_and_missing_reference(self):
        bad_parameter = experiments.ParameterSpec(
            id="bad", display_name="Bad", type="invalid", default=None
        )
        bad_experiment = replace(
            self.registry.experiments[0],
            parameters=(bad_parameter,),
            pipeline_ref="missing.pipeline",
        )
        bad_registry = replace(self.registry, experiments=(bad_experiment,) + self.registry.experiments[1:])
        errors = experiments.validate_registry(bad_registry)
        self.assertTrue(any("invalid parameter type" in error for error in errors))
        self.assertTrue(any("missing pipeline reference" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
