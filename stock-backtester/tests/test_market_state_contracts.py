"""Behavioral contracts for the historical MarketState research pipeline."""

from __future__ import annotations

import importlib
import math
import sys
import unittest
from dataclasses import fields
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


try:
    import numpy as np
    import pandas as pd

    NUMERICAL_DEPENDENCIES_AVAILABLE = True
except ImportError:
    np = None
    pd = None
    NUMERICAL_DEPENDENCIES_AVAILABLE = False


@unittest.skipUnless(
    NUMERICAL_DEPENDENCIES_AVAILABLE,
    "NumPy and Pandas are required for MarketState numerical contracts",
)
class MarketStateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.feature_script = importlib.import_module(
            "scripts.build_market_state_feature_matrix"
        )
        cls.portfolio_script = importlib.import_module(
            "scripts.backtest_market_state_portfolio"
        )
        cls.feature_module = importlib.import_module(
            "backtester.decision.market_state_features"
        )
        cls.portfolio_module = importlib.import_module(
            "backtester.backtests.market_state_portfolio"
        )
        cls.market_state_module = importlib.import_module(
            "backtester.decision.market_state"
        )
        cls.entropy_module = importlib.import_module(
            "backtester.decision.entropy_decision"
        )

    def test_script_helpers_reexport_canonical_package_functions(self) -> None:
        feature_names = (
            "build_feature_rows_for_ticker",
            "build_rebalance_dates",
            "compute_raw_momentum_scores",
            "entropy_decision_from_row",
        )
        for name in feature_names:
            self.assertIs(
                getattr(self.feature_script, name),
                getattr(self.feature_module, name),
            )

        portfolio_names = (
            "assign_weights",
            "build_rebalance_dates",
            "compute_market_state_for_date",
            "compute_portfolio_returns",
            "compute_raw_momentum_score",
            "import_compute_garch_metrics",
            "max_drawdown",
            "summarize_backtest",
        )
        for name in portfolio_names:
            self.assertIs(
                getattr(self.portfolio_script, name),
                getattr(self.portfolio_module, name),
            )

    def test_market_state_schema_aliases_and_exact_composition(self) -> None:
        entropy = self.entropy_module.EntropyDecision(
            entropy_regime="HIGH",
            direction_entropy_regime="NORMAL",
            entropy_state="RETURN_HIGH_DIRECTION_NORMAL",
            entropy_state_description="fixture",
            normalized_entropy=0.8,
            entropy_zscore=1.2,
            entropy_percentile=0.8,
            normalized_direction_entropy=0.5,
            direction_entropy_zscore=0.0,
            direction_entropy_percentile=0.5,
            signal_trust_multiplier=0.75,
            allow_new_signals=True,
            reason="fixture",
        )
        state = self.market_state_module.build_market_state(
            entropy,
            {
                "regime": "HIGH",
                "volatility_risk_multiplier": 0.8,
                "allow_equity": True,
                "allow_options": True,
                "preferred_strategy": "breakout",
            },
        )

        self.assertEqual(
            [field.name for field in fields(state)],
            [
                "volatility_regime",
                "entropy_state",
                "return_entropy_regime",
                "direction_entropy_regime",
                "risk_multiplier",
                "signal_trust_multiplier",
                "combined_multiplier",
                "allow_new_equity_positions",
                "allow_new_signals",
                "allow_options",
                "preferred_strategy",
                "capital_posture",
                "reason",
            ],
        )
        self.assertEqual(state.volatility_regime, "HIGH")
        self.assertAlmostEqual(state.combined_multiplier, 0.6)
        self.assertEqual(state.capital_posture, "DEFENSIVE")
        self.assertTrue(state.allow_new_equity_positions)
        self.assertTrue(state.allow_options)
        self.assertEqual(state.preferred_strategy, "breakout")
        self.assertEqual(
            state.reason,
            "volatility_regime=HIGH, entropy_state=RETURN_HIGH_DIRECTION_NORMAL, "
            "risk_multiplier=0.80, signal_trust_multiplier=0.75, "
            "combined_multiplier=0.60, capital_posture=DEFENSIVE",
        )

    def test_capital_posture_boundaries_and_restrictions(self) -> None:
        classify = self.market_state_module.classify_capital_posture
        cases = [
            (("NORMAL", "CALM", 1.01, True, True), "EXPANSIVE"),
            (("NORMAL", "CALM", 1.00, True, True), "NORMAL"),
            (("NORMAL", "CALM", 0.99, True, True), "CAUTIOUS"),
            (("NORMAL", "CALM", 0.75, True, True), "CAUTIOUS"),
            (("NORMAL", "CALM", 0.74, True, True), "DEFENSIVE"),
            (("NORMAL", "CALM", 0.50, True, True), "DEFENSIVE"),
            (("NORMAL", "CALM", 0.49, True, True), "CAPITAL_PRESERVATION"),
            (("EXTREME", "CALM", 1.00, True, True), "CAPITAL_PRESERVATION"),
            (("NORMAL", "RETURN_EXTREME", 0.50, True, True), "CAPITAL_PRESERVATION"),
            (("NORMAL", "CALM", 1.00, False, True), "RESTRICTED"),
            (("NORMAL", "CALM", 1.00, True, False), "RESTRICTED"),
        ]
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(classify(*arguments), expected)

    def test_rebalance_calendar_contract_and_shared_script_behavior(self) -> None:
        index = pd.bdate_range("2025-01-02", "2025-04-10")
        feature_builder = self.feature_module.build_rebalance_dates
        portfolio_builder = self.portfolio_module.build_rebalance_dates

        for frequency in ("D", "W", "B", "3W", "M", "6W", "Q"):
            feature_dates = feature_builder(index, "2025-01-02", "2025-04-10", frequency)
            portfolio_dates = portfolio_builder(index, "2025-01-02", "2025-04-10", frequency)
            self.assertEqual(feature_dates, portfolio_dates)

        self.assertEqual(
            feature_builder(index, "2025-01-02", "2025-04-10", "M"),
            [
                pd.Timestamp("2025-01-02"),
                pd.Timestamp("2025-02-03"),
                pd.Timestamp("2025-03-03"),
                pd.Timestamp("2025-04-01"),
            ],
        )
        self.assertEqual(feature_builder(index, "2026-01-01", "2026-02-01", "M"), [])
        with self.assertRaisesRegex(ValueError, "Unsupported rebalance frequency: X"):
            feature_builder(index, "2025-01-02", "2025-04-10", "X")

    def test_momentum_formulas_clipping_and_short_history(self) -> None:
        index = pd.bdate_range("2025-01-02", periods=70)
        prices = pd.DataFrame({"close": np.arange(100.0, 170.0)}, index=index)

        vector = self.feature_module.compute_raw_momentum_scores(prices)
        expected = 0.4 * (169.0 / 148.0 - 1.0) + 0.6 * (169.0 / 106.0 - 1.0)
        self.assertTrue(vector.iloc[:63].isna().all())
        self.assertAlmostEqual(float(vector.iloc[-1]), expected)
        self.assertAlmostEqual(
            self.portfolio_module.compute_raw_momentum_score(prices, index[-1]),
            expected,
        )
        self.assertEqual(
            self.portfolio_module.compute_raw_momentum_score(prices.iloc[:69], index[68]),
            0.0,
        )

        falling = pd.DataFrame({"close": np.arange(170.0, 100.0, -1.0)}, index=index)
        falling_scores = self.feature_module.compute_raw_momentum_scores(falling)
        self.assertEqual(float(falling_scores.iloc[-1]), 0.0)
        self.assertEqual(self.portfolio_module.compute_raw_momentum_score(falling, index[-1]), 0.0)

    def test_entropy_row_conversion_defaults_and_reason(self) -> None:
        decision = self.feature_module.entropy_decision_from_row(
            pd.Series(
                {
                    "entropy_regime": "HIGH",
                    "direction_entropy_regime": "LOW",
                    "entropy_state": "RETURN_HIGH_DIRECTION_LOW",
                    "signal_trust_multiplier": 0.75,
                }
            )
        )
        self.assertEqual(decision.entropy_regime, "HIGH")
        self.assertEqual(decision.direction_entropy_regime, "LOW")
        self.assertTrue(math.isnan(decision.normalized_entropy))
        self.assertTrue(decision.allow_new_signals)
        self.assertEqual(
            decision.reason,
            "entropy_state=RETURN_HIGH_DIRECTION_LOW, return_entropy_regime=HIGH, "
            "direction_entropy_regime=LOW, signal_trust_multiplier=0.75",
        )

    def test_feature_row_schema_asof_filtering_and_repeatability(self) -> None:
        index = pd.bdate_range("2024-01-02", periods=70)
        prices = pd.DataFrame({"close": np.arange(100.0, 170.0)}, index=index)
        vol_metrics = pd.DataFrame(
            {"vol_regime": "NORMAL", "vol_percentile": 0.5, "vol_zscore": 0.0},
            index=index,
        )
        entropy_metrics = pd.DataFrame(
            {
                "entropy_regime": "NORMAL",
                "direction_entropy_regime": "HIGH",
                "entropy_state": "RETURN_NORMAL_DIRECTION_HIGH",
                "entropy_state_description": "fixture",
                "normalized_entropy": 0.5,
                "entropy_zscore": 0.0,
                "entropy_percentile": 0.5,
                "normalized_direction_entropy": 0.8,
                "direction_entropy_zscore": 1.0,
                "direction_entropy_percentile": 0.8,
                "signal_trust_multiplier": 0.75,
            },
            index=index,
        )
        rebalance_dates = [index[-1], index[-1] + pd.Timedelta(days=3)]

        with (
            mock.patch.object(
                self.feature_module,
                "compute_fast_volatility_metrics",
                return_value=vol_metrics,
            ),
            mock.patch.object(
                self.feature_module,
                "compute_entropy_metrics",
                return_value=entropy_metrics,
            ),
            mock.patch.object(
                self.feature_module,
                "apply_entropy_decision_columns",
                side_effect=lambda frame: frame,
            ),
        ):
            first = self.feature_module.build_feature_rows_for_ticker(
                "XYZ", prices, rebalance_dates, mock.sentinel.entropy_config, 252
            )
            second = self.feature_module.build_feature_rows_for_ticker(
                "XYZ", prices, rebalance_dates, mock.sentinel.entropy_config, 252
            )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(
            list(first[0]),
            [
                "date",
                "asof_date",
                "ticker",
                "close",
                "raw_score",
                "adjusted_score",
                "vol_regime",
                "return_entropy_regime",
                "direction_entropy_regime",
                "entropy_state",
                "risk_multiplier",
                "signal_trust_multiplier",
                "combined_multiplier",
                "allow_new_equity_positions",
                "allow_options",
                "capital_posture",
                "preferred_strategy",
                "vol_percentile",
                "vol_zscore",
                "entropy_percentile",
                "direction_entropy_percentile",
            ],
        )
        self.assertEqual(first[1]["date"], rebalance_dates[1])
        self.assertEqual(first[1]["asof_date"], index[-1])
        self.assertEqual(first[0]["capital_posture"], "CAUTIOUS")
        self.assertAlmostEqual(first[0]["adjusted_score"], first[0]["raw_score"] * 0.75)

    def test_weight_assignment_preserves_caps_without_redistribution(self) -> None:
        rows = [
            {
                "ticker": "A",
                "allow_new_equity_positions": True,
                "adjusted_score": 3.0,
                "combined_multiplier": 0.8,
            },
            {
                "ticker": "B",
                "allow_new_equity_positions": True,
                "adjusted_score": 1.0,
                "combined_multiplier": 0.8,
            },
            {
                "ticker": "C",
                "allow_new_equity_positions": False,
                "adjusted_score": 2.0,
                "combined_multiplier": 0.8,
            },
        ]
        result = self.portfolio_module.assign_weights(rows, max_weight=0.35)
        self.assertEqual(result["ticker"].tolist(), ["A", "B", "C"])
        np.testing.assert_allclose(result["target_weight"], [0.35, 0.2, 0.0])
        self.assertAlmostEqual(float(result["target_weight"].sum()), 0.55)

    def test_portfolio_returns_one_day_lag_schema_and_summary(self) -> None:
        index = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
        data = {
            "A": pd.DataFrame({"close": [100.0, 110.0, 121.0]}, index=index),
            "B": pd.DataFrame({"close": [200.0, 180.0, 198.0]}, index=index),
        }
        curve = self.portfolio_module.compute_portfolio_returns(
            data,
            {index[0]: {"A": 0.5, "B": 0.5}},
            "2025-01-02",
            "2025-01-07",
            100.0,
        )
        self.assertEqual(list(curve.columns), ["portfolio_return", "equity"])
        np.testing.assert_allclose(
            curve["portfolio_return"],
            [0.0, 0.0, 0.1],
            atol=1e-12,
        )
        np.testing.assert_allclose(curve["equity"], [100.0, 100.0, 110.0])

        summary = self.portfolio_module.summarize_backtest(curve, 100.0)
        self.assertEqual(
            list(summary),
            [
                "start_equity",
                "final_equity",
                "total_return_pct",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
            ],
        )
        self.assertAlmostEqual(summary["total_return_pct"], 10.0)
        self.assertAlmostEqual(summary["max_drawdown_pct"], 0.0)
        expected_sharpe = (1.0 / 30.0) / np.std([0.0, 0.0, 0.1]) * np.sqrt(252)
        self.assertAlmostEqual(summary["sharpe"], expected_sharpe)


if __name__ == "__main__":
    unittest.main()
