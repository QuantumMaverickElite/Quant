from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from dataclasses import asdict
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - managed environments may omit pandas
    pd = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIVIDEND_ROOT = PROJECT_ROOT / "research" / "dividend_capture" / "src"


def load_module(name: str, relative_path: str):
    if "yfinance" not in sys.modules:
        sys.modules["yfinance"] = types.ModuleType("yfinance")
    path = DIVIDEND_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(pd is None, "pandas is not installed")
class DividendCaptureContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.naive = load_module(
            "dividend_naive_contract",
            "original_universe/naive_dividend_capture/backtest.py",
        )
        cls.regime = load_module(
            "dividend_regime_contract",
            "original_universe/regime_filtered/backtest.py",
        )
        cls.long_only = load_module(
            "dividend_long_only_contract",
            "original_universe/long_only_recovery/backtest.py",
        )

    def test_naive_calendar_and_trade_schema(self) -> None:
        index = pd.DatetimeIndex(["2024-01-02", "2024-01-04", "2024-01-05"])
        prices = pd.DataFrame({"Close": [10.0, 11.0, 12.0]}, index=index)

        self.assertEqual(
            self.naive.get_trading_day_index(prices, pd.Timestamp("2024-01-03")),
            1,
        )
        self.assertEqual(
            self.naive.get_trading_day_index(prices, pd.Timestamp("2024-01-04")),
            1,
        )
        self.assertIsNone(
            self.naive.get_trading_day_index(prices, pd.Timestamp("2024-01-06"))
        )

        aware = pd.DatetimeIndex(["2024-01-02"], tz="America/New_York")
        self.assertIsNone(self.naive.make_index_naive(aware).tz)

        trade = self.naive.TradeResult(
            ticker="ABC",
            ex_date="2024-01-04",
            buy_date="2024-01-03",
            sell_date="2024-01-05",
            dividend=1.0,
            buy_price=10.0,
            sell_price=10.5,
            shares=100.0,
            gross_pnl=150.0,
            gross_return_pct=1.5,
            drop_ratio=0.5,
        )
        self.assertEqual(
            list(asdict(trade)),
            [
                "ticker",
                "ex_date",
                "buy_date",
                "sell_date",
                "dividend",
                "buy_price",
                "sell_price",
                "shares",
                "gross_pnl",
                "gross_return_pct",
                "drop_ratio",
            ],
        )

    def test_regime_profiles_boundaries_and_shifted_window(self) -> None:
        profile_input = pd.DataFrame(
            {
                "ticker": ["A", "A", "B", "B", "C", "C"],
                "hold_days": [1, 3, 1, 3, 1, 3],
                "gross_return_pct": [1.0, 2.0, -1.0, -2.0, 1.0, -1.0],
            }
        )
        profiles = self.regime.label_ticker_profiles(profile_input)
        self.assertEqual(
            profiles[["ticker", "profile"]].to_dict("records"),
            [
                {"ticker": "A", "profile": "recovery"},
                {"ticker": "B", "profile": "continuation"},
                {"ticker": "C", "profile": "neutral"},
            ],
        )

        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        regime_input = pd.DataFrame(
            {
                "ex_date": dates,
                "hold_days": [1] * 5,
                "drop_ratio": [0.5, 1.0, 1.2, 0.4, 1.5],
            }
        )
        regimes = self.regime.build_regime_series(
            regime_input,
            rolling_window=2,
            overreaction_threshold=1.1,
            underreaction_threshold=0.9,
        )
        self.assertEqual(
            regimes["regime"].tolist(),
            ["unknown", "unknown", "underreaction", "neutral", "underreaction"],
        )
        self.assertTrue(pd.isna(regimes.loc[0, "rolling_drop_ratio"]))
        self.assertTrue(pd.isna(regimes.loc[1, "rolling_drop_ratio"]))
        self.assertAlmostEqual(regimes.loc[2, "rolling_drop_ratio"], 0.75)
        self.assertAlmostEqual(regimes.loc[3, "rolling_drop_ratio"], 1.1)

    def test_regime_strategy_long_short_skip_and_schema(self) -> None:
        dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        test_rows = pd.DataFrame(
            {
                "ticker": ["A", "B", "C"],
                "ex_date": dates,
                "hold_days": [1, 1, 1],
                "gross_return_pct": [2.0, -3.0, 4.0],
                "gross_pnl": [20.0, -30.0, 40.0],
            }
        )
        profiles = pd.DataFrame(
            {"ticker": ["A", "B", "C"], "profile": ["recovery", "continuation", "neutral"]}
        )
        regimes = pd.DataFrame(
            {
                "ex_date": dates,
                "rolling_drop_ratio": [0.8, 1.2, 1.0],
                "regime": ["underreaction", "overreaction", "neutral"],
            }
        )
        result = self.regime.apply_strategy(test_rows, profiles, regimes)
        self.assertEqual(result["signal"].tolist(), ["long", "short", "skip"])
        self.assertEqual(result["strategy_return_pct"].tolist(), [2.0, 3.0, 0.0])
        self.assertEqual(result["strategy_pnl"].tolist(), [20.0, 30.0, 0.0])
        self.assertEqual(
            result.columns.tolist(),
            [
                "ticker",
                "ex_date",
                "hold_days",
                "gross_return_pct",
                "gross_pnl",
                "profile",
                "rolling_drop_ratio",
                "regime",
                "signal",
                "strategy_return_pct",
                "strategy_pnl",
            ],
        )

    def test_long_only_profile_thresholds_and_two_signals(self) -> None:
        training = pd.DataFrame(
            {
                "ticker": ["A", "A", "A", "A", "B", "B"],
                "hold_days": [1, 1, 3, 3, 1, 3],
                "gross_return_pct": [1.0, -0.5, 2.0, -1.0, 0.0, 1.0],
            }
        )
        profiles = self.long_only.label_recovery_profiles(training)
        self.assertEqual(
            profiles[["ticker", "profile"]].to_dict("records"),
            [
                {"ticker": "A", "profile": "recovery"},
                {"ticker": "B", "profile": "neutral"},
            ],
        )
        self.assertAlmostEqual(profiles.loc[0, "hold_1_win_rate"], 0.5)

        dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        test_rows = pd.DataFrame(
            {
                "ticker": ["A", "A", "B"],
                "ex_date": dates,
                "hold_days": [1, 1, 1],
                "gross_return_pct": [2.0, -1.0, 3.0],
                "gross_pnl": [20.0, -10.0, 30.0],
            }
        )
        regimes = pd.DataFrame(
            {
                "ex_date": dates,
                "rolling_drop_ratio": [0.8, 1.0, 0.8],
                "regime": ["underreaction", "neutral", "underreaction"],
            }
        )
        result = self.long_only.apply_long_only_strategy(
            test_rows, profiles, regimes, trade_hold_days=1
        )
        self.assertEqual(result["signal_profile_only"].tolist(), ["long", "long", "skip"])
        self.assertEqual(result["signal_profile_regime"].tolist(), ["long", "skip", "skip"])
        self.assertEqual(result["return_profile_only"].tolist(), [2.0, -1.0, 0.0])
        self.assertEqual(result["pnl_profile_regime"].tolist(), [20.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
