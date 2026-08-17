"""Stdlib-only tests for typed experiment configurations."""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backtester.experiments import (
    ChoiceValue,
    ExperimentConfig,
    FixedValue,
    ParameterSpec,
    RandomValue,
    Registry,
    SweepValue,
    apply_overrides,
    build_registry,
    config_from_dict,
    config_to_json,
    default_config,
    validate_config,
)


class ParameterConfigTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry()

    def test_defaults_are_fixed_and_come_from_registry(self):
        config = default_config("intelligence.ml_policy.permutation", self.registry)
        self.assertEqual(config.parameters["permutations"], FixedValue(1000))
        self.assertEqual(config.parameters["seed"], FixedValue(42))

    def test_typed_overrides_and_unknown_parameters(self):
        config = default_config("signals.mean_reversion.peer_spread_baseline", self.registry)
        overridden = apply_overrides(config, ["min_peer_corr=0.45", "allow_short=true"], self.registry)
        self.assertEqual(overridden.parameters["min_peer_corr"], FixedValue(0.45))
        self.assertEqual(overridden.parameters["allow_short"], FixedValue(True))
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            apply_overrides(config, ["not_registered=1"], self.registry)

    def test_choice_and_sweep_validation(self):
        config = default_config("intelligence.ml_policy.sweep", self.registry)
        self.assertIsInstance(config.parameters["strengths"], ChoiceValue)
        bad = ExperimentConfig(
            config.experiment_id,
            {"strengths": SweepValue(1.0, 2.0, 0.0), "max_abs_deltas": config.parameters["max_abs_deltas"]},
        )
        errors = validate_config(bad, self.registry)
        self.assertTrue(any("zero step" in error for error in errors))

    def test_random_distribution_validation(self):
        parameter = ParameterSpec(
            id="x", display_name="X", type="float", default=0.5,
            supported_modes=("FIXED", "RANDOM"),
        )
        experiment = replace(self.registry.experiments[0], parameters=(parameter,))
        registry = Registry(experiments=(experiment,))
        valid = ExperimentConfig(experiment.id, {"x": RandomValue("uniform", 0.0, 1.0)})
        self.assertEqual(validate_config(valid, registry), [])
        invalid = ExperimentConfig(experiment.id, {"x": RandomValue("unsupported", 0.0, 1.0)})
        self.assertTrue(any("unsupported distribution" in error for error in validate_config(invalid, registry)))

    def test_json_round_trip_is_deterministic(self):
        config = apply_overrides(default_config("intelligence.ml_policy.permutation", self.registry), ["permutations=5000"], self.registry)
        first = config_to_json(config, self.registry)
        second = config_to_json(config_from_dict(json.loads(first), self.registry), self.registry)
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["parameters"]["permutations"]["value"], 5000)


if __name__ == "__main__":
    unittest.main()
