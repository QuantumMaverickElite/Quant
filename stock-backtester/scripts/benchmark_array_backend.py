from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from backtester.engines.array_backend import get_backend


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--feature-path",
        default="outputs/feature_matrix/rebalance_W/market_state_features.csv",
    )
    parser.add_argument(
        "--price-path",
        default="outputs/feature_matrix/rebalance_W/close_prices.csv",
    )
    parser.add_argument("--backend", choices=["numpy", "cupy"], default="numpy")
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument(
        "--tile-tickers",
        type=int,
        default=1,
        help="Repeat ticker columns to simulate a larger universe.",
    )
    parser.add_argument(
        "--tile-dates",
        type=int,
        default=1,
        help="Repeat rows to simulate a longer history.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backend = get_backend(args.backend)
    xp = backend.xp

    features = pd.read_csv(Path(args.feature_path))
    prices = pd.read_csv(Path(args.price_path), index_col=0)

    numeric_features = features.select_dtypes("number").to_numpy(dtype="float32")
    price_matrix = prices.to_numpy(dtype="float32")

    if args.tile_dates > 1:
        numeric_features = backend.xp.asnumpy(backend.asarray(numeric_features)) if backend.is_gpu else numeric_features
        price_matrix = backend.xp.asnumpy(backend.asarray(price_matrix)) if backend.is_gpu else price_matrix

        import numpy as np

        numeric_features = np.tile(numeric_features, (args.tile_dates, 1))
        price_matrix = np.tile(price_matrix, (args.tile_dates, 1))

    if args.tile_tickers > 1:
        import numpy as np

        price_matrix = np.tile(price_matrix, (1, args.tile_tickers))

    x_features = backend.asarray(numeric_features)
    x_prices = backend.asarray(price_matrix)

    backend.synchronize()

    print(f"Backend: {backend.name}")
    print(f"Feature matrix shape: {numeric_features.shape}")
    print(f"Price matrix shape: {price_matrix.shape}")
    print(f"Repeats: {args.repeats}")
    print(f"Tile tickers: {args.tile_tickers}")
    print(f"Tile dates: {args.tile_dates}")

    t0 = time.perf_counter()

    result = None
    for _ in range(args.repeats):
        # GPU-friendly dense operations.
        feature_means = xp.nanmean(x_features, axis=0)
        price_returns = x_prices[1:] / x_prices[:-1] - 1.0
        return_means = xp.nanmean(price_returns, axis=0)

        # Force some actual work to survive lazy behavior.
        result = xp.nanmean(feature_means) + xp.nanmean(return_means)

    backend.synchronize()
    t1 = time.perf_counter()

    result_cpu = backend.to_cpu(result)

    print(f"Result checksum: {float(result_cpu):.8f}")
    print(f"Elapsed seconds: {t1 - t0:.6f}")
    print(f"Ops/sec: {args.repeats / (t1 - t0):.2f}")


if __name__ == "__main__":
    main()
