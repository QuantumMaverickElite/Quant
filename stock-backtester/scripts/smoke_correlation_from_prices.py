# scripts/smoke_correlation_from_prices.py

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.correlation import (
    CorrelationTracker,
    CorrelationTrackerConfig,
    build_asset_metadata,
    prices_to_return_matrix,
)


def main() -> None:
    rng = np.random.default_rng(42)

    dates = pd.date_range("2023-01-01", periods=300, freq="B")
    tickers = ["AAPL", "MSFT", "NVDA", "JPM", "BAC", "XOM"]

    market = rng.normal(0.0003, 0.01, size=(len(dates), 1))
    noise = rng.normal(0.0001, 0.015, size=(len(dates), len(tickers)))
    returns = market + noise

    prices = 100.0 * np.cumprod(1.0 + returns, axis=0)

    price_frame = pd.DataFrame(prices, index=dates, columns=tickers)

    return_matrix = prices_to_return_matrix(price_frame)

    metadata = build_asset_metadata(
        tickers=return_matrix.tickers,
        sectors={
            "AAPL": "Technology",
            "MSFT": "Technology",
            "NVDA": "Technology",
            "JPM": "Financial Services",
            "BAC": "Financial Services",
            "XOM": "Energy",
        },
        industries={
            "AAPL": "Consumer Electronics",
            "MSFT": "Software",
            "NVDA": "Semiconductors",
            "JPM": "Banks",
            "BAC": "Banks",
            "XOM": "Oil & Gas Integrated",
        },
    )

    tracker = CorrelationTracker(
        CorrelationTrackerConfig(
            windows=(20, 60, 120),
            step=5,
            top_k=3,
            backend="numpy",
        )
    )

    features = tracker.compute_features(return_matrix, metadata)

    print(features.head(20))
    print()
    print(features.tail(20))
    print()
    print(features.info())


if __name__ == "__main__":
    main()
