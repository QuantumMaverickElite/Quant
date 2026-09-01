"""Contracts for the daily overlapping mean-reversion portfolio evaluator."""

from __future__ import annotations

import importlib
import sys
import unittest
from dataclasses import fields
from pathlib import Path


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
    "NumPy and Pandas are required for portfolio numerical contracts",
)
class MeanReversionDailyPortfolioContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = importlib.import_module(
            "scripts.backtest_mean_reversion_daily_portfolio"
        )
        cls.implementation = importlib.import_module(
            "backtester.backtests.mean_reversion_daily_portfolio"
        )

    def test_script_helpers_reexport_package_implementation(self) -> None:
        for name in (
            "OpenPosition",
            "prepare_orders",
            "mark_to_market",
            "run_daily_portfolio_backtest",
            "summarize_daily_backtest",
        ):
            self.assertIs(
                getattr(self.script, name),
                getattr(self.implementation, name),
            )

    @staticmethod
    def price_fixture() -> pd.DataFrame:
        index = pd.bdate_range("2025-01-02", periods=7)
        return pd.DataFrame(
            {
                "AAA": [98.0, 100.0, 105.0, 110.0, 109.0, 108.0, 107.0],
                "BBB": [52.0, 50.0, 50.0, 45.0, 46.0, 47.0, 48.0],
                "CCC": [20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
            },
            index=index,
        )

    def test_open_position_schema_is_stable(self) -> None:
        self.assertEqual(
            [field.name for field in fields(self.implementation.OpenPosition)],
            [
                "ticker",
                "entry_date",
                "exit_date",
                "shares",
                "entry_price",
                "entry_value",
                "adjusted_confidence",
                "signal_date",
                "peer_spread_z",
            ],
        )

    def test_prepare_orders_filters_ranks_and_uses_trading_day_lag(self) -> None:
        prices = self.price_fixture()
        signal_date = prices.index[0]
        signals = pd.DataFrame(
            [
                {
                    "date": signal_date,
                    "ticker": "CCC",
                    "horizon": 5,
                    "adjusted_confidence": 0.4,
                    "peer_spread_z": -1.0,
                },
                {
                    "date": signal_date,
                    "ticker": "BBB",
                    "horizon": 5,
                    "adjusted_confidence": 0.6,
                    "peer_spread_z": 1.5,
                },
                {
                    "date": signal_date,
                    "ticker": "AAA",
                    "horizon": 5,
                    "adjusted_confidence": 0.9,
                    "peer_spread_z": -2.0,
                },
                {
                    "date": signal_date,
                    "ticker": "LOW",
                    "horizon": 5,
                    "adjusted_confidence": 0.09,
                    "peer_spread_z": 0.0,
                },
                {
                    "date": signal_date,
                    "ticker": "H10",
                    "horizon": 10,
                    "adjusted_confidence": 1.0,
                    "peer_spread_z": 0.0,
                },
                {
                    "date": "2025-01-04",
                    "ticker": "WEEKEND",
                    "horizon": 5,
                    "adjusted_confidence": 1.0,
                    "peer_spread_z": 0.0,
                },
                {
                    "date": prices.index[-2],
                    "ticker": "LATE",
                    "horizon": 5,
                    "adjusted_confidence": 1.0,
                    "peer_spread_z": 0.0,
                },
            ]
        )

        orders = self.implementation.prepare_orders(
            signals,
            prices,
            signal_horizon=5,
            hold_days=2,
            min_adjusted_confidence=0.10,
            top_n_per_date=2,
        )

        self.assertEqual(orders["ticker"].tolist(), ["AAA", "BBB"])
        self.assertEqual(orders["signal_date"].tolist(), [signal_date, signal_date])
        self.assertEqual(orders["entry_date"].tolist(), [prices.index[1], prices.index[1]])
        self.assertEqual(orders["exit_date"].tolist(), [prices.index[3], prices.index[3]])
        self.assertEqual(
            list(orders.columns),
            [
                "date",
                "ticker",
                "horizon",
                "adjusted_confidence",
                "peer_spread_z",
                "signal_date",
                "entry_date",
                "exit_date",
            ],
        )

    def test_prepare_orders_preserves_duplicate_rows(self) -> None:
        prices = self.price_fixture()
        row = {
            "date": prices.index[0],
            "ticker": "AAA",
            "horizon": 5,
            "adjusted_confidence": 0.8,
            "peer_spread_z": -2.0,
        }
        orders = self.implementation.prepare_orders(
            pd.DataFrame([row, row]),
            prices,
            signal_horizon=5,
            hold_days=1,
            min_adjusted_confidence=0.1,
            top_n_per_date=5,
        )
        self.assertEqual(orders["ticker"].tolist(), ["AAA", "AAA"])

    def test_mark_to_market_uses_entry_price_for_missing_daily_price(self) -> None:
        prices = self.price_fixture()
        date = prices.index[2]
        prices.loc[date, "AAA"] = np.nan
        position = self.implementation.OpenPosition(
            ticker="AAA",
            entry_date=prices.index[1],
            exit_date=prices.index[3],
            shares=3.0,
            entry_price=100.0,
            entry_value=300.0,
            adjusted_confidence=0.75,
            signal_date=prices.index[0],
            peer_spread_z=-2.0,
        )
        self.assertEqual(
            self.implementation.mark_to_market([position], prices, date),
            300.0,
        )

    def test_portfolio_contract_caps_without_redistribution_and_closes_first(self) -> None:
        prices = self.price_fixture()
        orders = pd.DataFrame(
            [
                {
                    "ticker": "AAA",
                    "adjusted_confidence": 0.75,
                    "peer_spread_z": -2.0,
                    "signal_date": prices.index[0],
                    "entry_date": prices.index[1],
                    "exit_date": prices.index[3],
                },
                {
                    "ticker": "BBB",
                    "adjusted_confidence": 0.25,
                    "peer_spread_z": 2.0,
                    "signal_date": prices.index[0],
                    "entry_date": prices.index[1],
                    "exit_date": prices.index[3],
                },
            ]
        )

        trades, equity = self.implementation.run_daily_portfolio_backtest(
            orders,
            prices,
            initial_capital=1000.0,
            max_gross_exposure=1.0,
            target_new_basket_exposure=0.5,
            max_position_weight=0.3,
            fee_bps=0.0,
        )

        self.assertEqual(trades["ticker"].tolist(), ["AAA", "BBB"])
        np.testing.assert_allclose(trades["entry_value"], [300.0, 125.0])
        np.testing.assert_allclose(trades["exit_value"], [330.0, 112.5])
        np.testing.assert_allclose(trades["pnl"], [30.0, -12.5])
        self.assertEqual(
            list(trades.columns),
            [
                "signal_date",
                "entry_date",
                "exit_date",
                "ticker",
                "shares",
                "entry_price",
                "exit_price",
                "entry_value",
                "exit_value",
                "pnl",
                "trade_return",
                "adjusted_confidence",
                "peer_spread_z",
            ],
        )
        self.assertEqual(
            list(equity.columns),
            [
                "date",
                "cash",
                "open_value",
                "equity",
                "gross_exposure",
                "open_positions",
                "daily_return",
                "cum_return",
                "running_max",
                "drawdown",
            ],
        )
        np.testing.assert_allclose(
            equity["equity"],
            [1000.0, 1000.0, 1015.0, 1017.5, 1017.5, 1017.5, 1017.5],
        )
        np.testing.assert_allclose(
            equity["gross_exposure"],
            [0.0, 0.425, 440.0 / 1015.0, 0.0, 0.0, 0.0, 0.0],
        )
        self.assertEqual(equity["open_positions"].tolist(), [0, 2, 2, 0, 0, 0, 0])

    def test_entry_and_exit_fees_keep_historical_trade_return_semantics(self) -> None:
        prices = self.price_fixture()[["AAA"]]
        orders = pd.DataFrame(
            [
                {
                    "ticker": "AAA",
                    "adjusted_confidence": 1.0,
                    "peer_spread_z": -2.0,
                    "signal_date": prices.index[0],
                    "entry_date": prices.index[1],
                    "exit_date": prices.index[3],
                }
            ]
        )
        trades, equity = self.implementation.run_daily_portfolio_backtest(
            orders,
            prices,
            initial_capital=1000.0,
            max_gross_exposure=1.0,
            target_new_basket_exposure=0.5,
            max_position_weight=0.5,
            fee_bps=100.0,
        )
        self.assertAlmostEqual(float(trades.loc[0, "entry_value"]), 500.0)
        self.assertAlmostEqual(float(trades.loc[0, "exit_value"]), 544.5)
        self.assertAlmostEqual(float(trades.loc[0, "pnl"]), 44.5)
        self.assertAlmostEqual(float(trades.loc[0, "trade_return"]), 0.089)
        self.assertAlmostEqual(float(equity.iloc[-1]["equity"]), 1039.5)

    def test_summary_schema_and_conditional_trade_metrics(self) -> None:
        prices = self.price_fixture()
        equity = pd.DataFrame(
            {
                "date": prices.index[:3],
                "equity": [1000.0, 1010.0, 1005.0],
                "daily_return": [0.0, 0.01, 1005.0 / 1010.0 - 1.0],
                "drawdown": [0.0, 0.0, 1005.0 / 1010.0 - 1.0],
                "gross_exposure": [0.0, 0.4, 0.0],
                "open_positions": [0, 2, 0],
            }
        )
        trades = pd.DataFrame(
            {"pnl": [10.0, -5.0], "trade_return": [0.10, -0.05]}
        )
        summary = self.implementation.summarize_daily_backtest(
            trades,
            equity,
            initial_capital=1000.0,
        )
        self.assertEqual(
            list(summary.columns),
            [
                "final_equity",
                "total_return",
                "cagr",
                "daily_vol",
                "sharpe",
                "max_drawdown",
                "avg_gross_exposure",
                "max_gross_exposure",
                "avg_open_positions",
                "max_open_positions",
                "num_closed_trades",
                "trade_win_rate",
                "avg_trade_return",
                "median_trade_return",
                "avg_trade_pnl",
            ],
        )
        self.assertAlmostEqual(float(summary.loc[0, "final_equity"]), 1005.0)
        self.assertAlmostEqual(float(summary.loc[0, "total_return"]), 0.005)
        self.assertAlmostEqual(float(summary.loc[0, "trade_win_rate"]), 0.5)
        self.assertAlmostEqual(float(summary.loc[0, "avg_trade_pnl"]), 2.5)

    def test_repeated_execution_is_deterministic(self) -> None:
        prices = self.price_fixture()
        signals = pd.DataFrame(
            [
                {
                    "date": prices.index[0],
                    "ticker": "AAA",
                    "horizon": 5,
                    "adjusted_confidence": 0.75,
                    "peer_spread_z": -2.0,
                },
                {
                    "date": prices.index[0],
                    "ticker": "BBB",
                    "horizon": 5,
                    "adjusted_confidence": 0.25,
                    "peer_spread_z": 2.0,
                },
            ]
        )
        orders = self.implementation.prepare_orders(
            signals,
            prices,
            signal_horizon=5,
            hold_days=2,
            min_adjusted_confidence=0.1,
            top_n_per_date=5,
        )
        kwargs = {
            "initial_capital": 1000.0,
            "max_gross_exposure": 1.0,
            "target_new_basket_exposure": 0.5,
            "max_position_weight": 0.3,
            "fee_bps": 0.0,
        }
        first = self.implementation.run_daily_portfolio_backtest(
            orders, prices, **kwargs
        )
        second = self.implementation.run_daily_portfolio_backtest(
            orders, prices, **kwargs
        )
        pd.testing.assert_frame_equal(first[0], second[0])
        pd.testing.assert_frame_equal(first[1], second[1])


if __name__ == "__main__":
    unittest.main()
