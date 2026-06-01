# scripts/smoke_correlation_tracker.py

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.correlation import (
    AssetMetadata,
    CorrelationTracker,
    CorrelationTrackerConfig,
    ReturnMatrix,
)


def main() -> None:
    rng = np.random.default_rng(42)

    dates = pd.date_range("2024-01-01", periods=150, freq="B")
    tickers = ["AAPL", "MSFT", "NVDA", "JPM", "BAC", "XOM"]

    market = rng.normal(0, 0.01, size=(150, 1))
    noise = rng.normal(0, 0.01, size=(150, len(tickers)))

    returns = market + noise

    return_matrix = ReturnMatrix(
        values=returns.astype(np.float32),
        dates=dates,
        tickers=tickers,
    )

    metadata = AssetMetadata(
        tickers=tickers,
        sector_codes=np.array([0, 0, 0, 1, 1, 2], dtype=np.int32),
        industry_codes=np.array([0, 0, 1, 2, 2, 3], dtype=np.int32),
    )

    tracker = CorrelationTracker(
        CorrelationTrackerConfig(
            windows=(20, 60),
            step=5,
            top_k=3,
            backend="numpy",
        )
    )

    features = tracker.compute_features(return_matrix, metadata)

    print(features.head(20))
    print()
    print(features.info())


if __name__ == "__main__":
    main()
