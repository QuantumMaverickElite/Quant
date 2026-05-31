from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backtester.engines.array_backend import get_backend
from backtester.engines.matrix_batch_ops import (
    compute_return_matrix,
    equal_weight_from_mask,
    equity_curve_from_returns,
    portfolio_returns_from_weights,
    top_n_mask_from_scores,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--price-path",
        default="outputs/feature_matrix/rebalance_W/close_prices.csv",
    )
    parser.add_argument("--backend", choices=["numpy", "cupy"], default="numpy")
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--tile-tickers", type=int, default=1)
    parser.add_argument("--tile-dates", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backend = get_backend(args.backend)

    prices_df = pd.read_csv(Path(args.price_path), index_col=0)
    prices_df = prices_df.ffill().bfill()
    prices = prices_df.to_numpy(dtype=np.float32)

    if args.tile_dates > 1:
        prices = np.tile(prices, (args.tile_dates, 1))

    if args.tile_tickers > 1:
        prices = np.tile(prices, (1, args.tile_tickers))

    # Fake score matrix for benchmarking:
    # same date x ticker shape as returns after first row.
    returns_np = prices[1:] / prices[:-1] - 1.0
    returns_np = np.nan_to_num(returns_np, nan=0.0, posinf=0.0, neginf=0.0)

    # This is a backend benchmark, not a real strategy.
    # Clip extreme returns so the fake equity curve does not overflow.
    returns_np = np.clip(returns_np, -0.25, 0.25).astype(np.float32)

    # Use bounded deterministic synthetic scores. This avoids selecting
    # absurd repeated return outliers when ticker columns are tiled.
    rng = np.random.default_rng(42)
    scores_np = rng.normal(
        loc=0.0,
        scale=1.0,
        size=returns_np.shape,
    ).astype(np.float32)

    x_prices = backend.asarray(prices, dtype=backend.xp.float32)
    x_scores = backend.asarray(scores_np, dtype=backend.xp.float32)

    backend.synchronize()

    print(f"Backend: {backend.name}")
    print(f"Prices shape: {prices.shape}")
    print(f"Scores shape: {scores_np.shape}")
    print(f"Top N: {args.top_n}")
    print(f"Repeats: {args.repeats}")
    print(f"Tile tickers: {args.tile_tickers}")
    print(f"Tile dates: {args.tile_dates}")

    t0 = time.perf_counter()

    equity = None
    for _ in range(args.repeats):
        returns = compute_return_matrix(x_prices, backend)
        mask = top_n_mask_from_scores(x_scores, args.top_n, backend)
        weights = equal_weight_from_mask(mask, backend)
        portfolio_returns = portfolio_returns_from_weights(weights, returns, backend)
        equity = equity_curve_from_returns(portfolio_returns, backend)

    backend.synchronize()
    t1 = time.perf_counter()

    equity_cpu = backend.to_cpu(equity)
    print(f"Final equity checksum: {float(equity_cpu[-1]):.4f}")
    print(f"Elapsed seconds: {t1 - t0:.6f}")
    print(f"Ops/sec: {args.repeats / (t1 - t0):.2f}")


if __name__ == "__main__":
    main()
