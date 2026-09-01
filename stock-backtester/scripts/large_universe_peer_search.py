# scripts/large_universe_peer_search.py

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from backtester.correlation.peer_search import (
    compute_top_peers,
    dtype_from_name,
    load_returns_matrix,
    standardize_window,
    top_k_from_corr_block,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find top correlated peers from a large-universe returns matrix."
    )

    parser.add_argument(
        "--returns-meta",
        required=True,
        help="Path to returns_meta.json.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for peer search results.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=252,
        help="Number of trailing return rows to use.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of peers to keep per ticker.",
    )
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=200,
        help="Minimum overlapping finite return observations required.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=512,
        help="Ticker block size for correlation computation.",
    )
    parser.add_argument(
        "--min-abs-corr",
        type=float,
        default=0.0,
        help="Optional minimum absolute correlation threshold.",
    )
    parser.add_argument(
        "--positive-only",
        action="store_true",
        help="Keep only positive correlations.",
    )
    parser.add_argument(
        "--save-csv",
        action="store_true",
        default=True,
        help="Save peers.csv.",
    )
    parser.add_argument(
        "--save-parquet",
        action="store_true",
        default=True,
        help="Save peers.parquet if parquet engine is available.",
    )

    return parser.parse_args()


def save_outputs(
    peers: pd.DataFrame,
    out_dir: Path,
    *,
    save_csv: bool,
    save_parquet: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    if save_csv:
        csv_path = out_dir / "peers.csv"
        peers.to_csv(csv_path, index=False)
        print(f"Saved CSV: {csv_path}")

    if save_parquet:
        parquet_path = out_dir / "peers.parquet"

        try:
            peers.to_parquet(parquet_path, index=False)
            print(f"Saved parquet: {parquet_path}")
        except Exception as exc:
            print(f"Skipping parquet save because it failed: {exc!r}")


def main() -> None:
    args = parse_args()

    returns_meta_path = Path(args.returns_meta)
    out_dir = Path(args.out_dir)

    returns, meta = load_returns_matrix(returns_meta_path)

    tickers = list(meta["tickers"])
    dates = list(meta["dates"])

    print()
    print("=" * 80)
    print("Large-Universe Peer Search")
    print("=" * 80)
    print(f"Returns matrix: {returns.shape[0]:,} rows × {returns.shape[1]:,} tickers")
    print(f"Returns meta: {returns_meta_path}")

    started = time.perf_counter()

    peers = compute_top_peers(
        returns,
        tickers,
        dates,
        window=args.window,
        top_k=args.top_k,
        min_overlap=args.min_overlap,
        block_size=args.block_size,
        min_abs_corr=args.min_abs_corr,
        positive_only=args.positive_only,
    )

    elapsed = time.perf_counter() - started

    save_outputs(
        peers,
        out_dir,
        save_csv=args.save_csv,
        save_parquet=args.save_parquet,
    )

    print()
    print("=" * 80)
    print("Peer search complete")
    print("=" * 80)
    print(f"Rows: {len(peers):,}")
    print(f"Unique tickers: {peers['ticker'].nunique() if not peers.empty else 0:,}")
    print(f"Elapsed: {elapsed:.2f}s")

    if not peers.empty:
        print()
        print("Highest correlations:")
        print(
            peers.sort_values("corr", ascending=False).head(20).to_string(index=False)
        )

        print()
        print("Sample peers:")
        print(peers.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
