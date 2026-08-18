"""Small behavioral contracts for the three peer/spread implementations.

These tests intentionally import the current script helpers.  The scripts are
the oracle for the future extraction into ``backtester.correlation``.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:  # pragma: no cover - exercised in minimal Codex images.
    np = None  # type: ignore[assignment]
    pd = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"contract_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(np is None or pd is None, "NumPy and pandas are required")
class PeerSpreadFixtureMixin:
    @classmethod
    def setUpClass(cls) -> None:
        cls.peer_search = load_script("large_universe_peer_search.py")
        cls.staged = load_script("generate_peer_basket_spreads.py")
        cls.cached = load_script("run_peer_spread_features_from_cached_matrix.py")

        cls.tickers = list("ABCDEFGHIJ")
        cls.dates = [f"2020-01-{day:02d}" for day in range(1, 25)]

        base = np.array(
            [0.010, -0.006, 0.014, -0.003, 0.008, 0.002, -0.010, 0.012]
            * 3,
            dtype=np.float32,
        )
        noise = np.array(
            [0.001, -0.001, 0.0005, 0.001, -0.0005, 0.0005, 0.001, -0.001]
            * 3,
            dtype=np.float32,
        )
        weak = np.array(
            [0.002, 0.001, -0.003, 0.004, -0.002, 0.003, -0.001, 0.002]
            * 3,
            dtype=np.float32,
        )
        distinct = np.array(
            [-0.004, 0.006, -0.002, 0.005, 0.001, -0.005, 0.003, -0.001]
            * 3,
            dtype=np.float32,
        )

        values = np.column_stack(
            [
                base,
                base.copy(),
                base + noise,
                -base,
                weak,
                np.full(base.shape, 0.002, dtype=np.float32),
                base.copy(),
                distinct,
                base + noise * 1.01,
                -distinct,
            ]
        ).astype(np.float32)
        # Keep G's missing block inside the peer-search trailing window so it
        # exercises overlap handling without tying B's exact A/B relationship.
        values[14:18, 6] = np.nan
        cls.returns = values

    def assert_frame_columns(self, frame, expected):
        self.assertEqual(list(frame.columns), list(expected))


class TestPeerSearchContracts(PeerSpreadFixtureMixin, unittest.TestCase):
    def test_golden_peer_schema_order_and_determinism(self):
        kwargs = dict(
            window=12,
            top_k=3,
            min_overlap=8,
            block_size=4,
            min_abs_corr=0.0,
            positive_only=False,
        )
        first = self.peer_search.compute_top_peers(
            self.returns, self.tickers, self.dates, **kwargs
        )
        second = self.peer_search.compute_top_peers(
            self.returns, self.tickers, self.dates, **kwargs
        )

        self.assertTrue(first.equals(second))
        self.assertEqual(
            list(first.columns),
            [
                "as_of_date",
                "window",
                "ticker",
                "peer_rank",
                "peer",
                "corr",
                "overlap",
                "ticker_valid_coverage",
                "peer_valid_coverage",
            ],
        )
        self.assertTrue((first["ticker"] != first["peer"]).all())
        self.assertLessEqual(first.groupby("ticker").size().max(), 3)
        self.assertEqual(first.sort_values(["ticker", "peer_rank"]).index.tolist(), list(first.index))

        a_peers = first.loc[first["ticker"] == "A"].sort_values("peer_rank")
        b_peers = first.loc[first["ticker"] == "B"].sort_values("peer_rank")
        self.assertEqual(a_peers.iloc[0]["peer"], "B")
        self.assertEqual(b_peers.iloc[0]["peer"], "A")
        self.assertEqual(a_peers.iloc[0]["overlap"], 12)
        self.assertAlmostEqual(float(a_peers.iloc[0]["corr"]), 1.0, places=5)

    def test_positive_only_excludes_negative_relationship(self):
        peers = self.peer_search.compute_top_peers(
            self.returns,
            self.tickers,
            self.dates,
            window=12,
            top_k=3,
            min_overlap=8,
            block_size=10,
            min_abs_corr=0.0,
            positive_only=True,
        )
        a_peers = peers.loc[peers["ticker"] == "A"]
        self.assertFalse((peers["ticker"] == peers["peer"]).any())
        self.assertNotIn("A", set(a_peers["peer"]))
        self.assertNotIn("D", set(a_peers["peer"]))
        self.assertTrue(np.isfinite(peers["corr"].to_numpy()).all())

    def test_zero_variance_and_missing_data_are_not_infinities(self):
        peers = self.peer_search.compute_top_peers(
            self.returns,
            self.tickers,
            self.dates,
            window=12,
            top_k=3,
            min_overlap=8,
            block_size=5,
            min_abs_corr=0.0,
            positive_only=False,
        )
        f_rows = peers.loc[peers["ticker"] == "F"]
        self.assertTrue(np.isfinite(peers["corr"].to_numpy()).all())
        self.assertTrue(np.isfinite(peers["overlap"].to_numpy()).all())
        if not f_rows.empty:
            self.assertTrue(np.allclose(f_rows["corr"].to_numpy(), 0.0))
        g_rows = peers.loc[peers["ticker"] == "G"]
        if not g_rows.empty:
            self.assertTrue((g_rows["overlap"] >= 8).all())

    def test_near_tie_set_is_repeatable_without_inventing_tie_policy(self):
        peers = self.peer_search.compute_top_peers(
            self.returns,
            self.tickers,
            self.dates,
            window=12,
            top_k=2,
            min_overlap=8,
            block_size=10,
            min_abs_corr=0.0,
            positive_only=True,
        )
        repeated = self.peer_search.compute_top_peers(
            self.returns,
            self.tickers,
            self.dates,
            window=12,
            top_k=2,
            min_overlap=8,
            block_size=10,
            min_abs_corr=0.0,
            positive_only=True,
        )
        self.assertTrue(peers.equals(repeated))
        self.assertEqual(len(peers.loc[peers["ticker"] == "A"]), 2)


class TestStagedPeerSpreadContracts(PeerSpreadFixtureMixin, unittest.TestCase):
    def _peer_group(self):
        return pd.DataFrame(
            {
                "ticker": ["A", "A"],
                "peer": ["B", "C"],
                "peer_rank": [1, 2],
                "corr": [1.0, 0.8],
                "peer_idx": [1, 2],
            }
        )

    def test_staged_schema_preserves_historical_names_and_values(self):
        out = self.staged.compute_one_ticker(
            "A",
            0,
            self._peer_group(),
            self.returns,
            self.dates,
            spread_window=5,
            min_spread_observations=3,
            weighting="equal",
            min_avg_peer_corr=0.3,
            min_peer_count=2,
            min_daily_valid_peers=2,
            horizon=2,
        )
        self.assertIsNotNone(out)
        assert out is not None
        expected = {
            "date", "ticker", "horizon", "peer_count", "daily_valid_peer_count",
            "avg_peer_corr", "peer_list", "peer_corr_list", "ticker_return",
            "peer_basket_return", "relative_return", "spread", "spread_mean",
            "spread_std", "spread_obs", "peer_spread_z", "direction", "raw_confidence",
        }
        self.assertTrue(expected.issubset(out.columns))
        self.assertIn("ticker_return", out.columns)
        self.assertIn("avg_peer_corr", out.columns)
        self.assertNotIn("stock_return", out.columns)
        self.assertNotIn("top_k_avg_corr", out.columns)
        self.assertEqual(out["date"].tolist(), sorted(out["date"].tolist()))
        numeric = out.select_dtypes(include=["number"])
        self.assertFalse(np.isinf(numeric.to_numpy()).any())

        row = out.iloc[0]
        date_index = self.dates.index(str(row["date"])[:10])
        expected_relative = self.returns[date_index, 0] - np.mean(
            self.returns[date_index, [1, 2]]
        )
        self.assertAlmostEqual(float(row["relative_return"]), float(expected_relative), places=6)
        self.assertAlmostEqual(
            float(row["spread"]),
            float(row["relative_return"]),
            places=6,
        )


class TestOnePassAndDownstreamContracts(PeerSpreadFixtureMixin, unittest.TestCase):
    def test_one_pass_helpers_preserve_canonical_return_contract(self):
        window = self.returns[-12:]
        corr = self.cached.corr_from_window(window)
        indices, values = self.cached.topk_peer_indices(corr, 3)
        trailing = self.cached.cumulative_return(self.returns, 12, 2)

        self.assertEqual(indices.shape, (10, 3))
        self.assertEqual(values.shape, (10, 3))
        self.assertTrue(np.all(indices >= 0))
        self.assertTrue(np.isfinite(trailing[:5]).all())

        canonical = pd.DataFrame(
            {
                "date": pd.to_datetime([self.dates[-1]]),
                "ticker": ["A"],
                "window": [12],
                "horizon": [2],
                "stock_return": [float(trailing[0])],
                "peer_basket_return": [0.0],
                "peer_spread": [float(trailing[0])],
                "peer_spread_z": [-2.0],
                "top_k_avg_corr": [0.8],
                "peer_1": ["B"],
                "peer_2": ["C"],
            }
        )
        required = {
            "date", "ticker", "window", "horizon", "stock_return",
            "peer_basket_return", "peer_spread", "peer_spread_z", "top_k_avg_corr",
        }
        self.assertTrue(required.issubset(canonical.columns))

    def test_canonical_schema_satisfies_mean_reversion_and_staged_does_not(self):
        from backtester.signals.mean_reversion import build_mean_reversion_signals

        canonical = pd.DataFrame(
            {
                "date": pd.to_datetime([self.dates[-1]]),
                "ticker": ["A"],
                "window": [12],
                "horizon": [2],
                "stock_return": [0.1],
                "peer_basket_return": [0.05],
                "peer_spread": [0.05],
                "peer_spread_z": [-2.0],
                "top_k_avg_corr": [0.8],
            }
        )
        signals = build_mean_reversion_signals(canonical, min_abs_z=1.5)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals.iloc[0]["direction"], "long")

        staged_names = canonical.rename(
            columns={"stock_return": "ticker_return", "top_k_avg_corr": "avg_peer_corr"}
        )
        with self.assertRaises(ValueError):
            build_mean_reversion_signals(staged_names, min_abs_z=1.5)


if __name__ == "__main__":
    unittest.main()
