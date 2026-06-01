# scripts/large_universe_peer_search.py

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd


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


def dtype_from_name(name: str) -> type[np.float32] | type[np.float64]:
    if name == "float32":
        return np.float32
    if name == "float64":
        return np.float64
    raise ValueError(f"Unsupported dtype: {name}")


def load_returns_matrix(meta_path: Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(meta_path.read_text())

    dtype = dtype_from_name(meta["dtype"])

    raw = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    expected = int(meta["rows"]) * int(meta["cols"])

    if raw.size != expected:
        raise RuntimeError(
            f"Returns binary size mismatch: got {raw.size} values, expected {expected}."
        )

    returns = raw.reshape(int(meta["rows"]), int(meta["cols"]))

    return returns.astype(np.float32, copy=False), meta


def standardize_window(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    finite = np.isfinite(x)

    valid_counts = finite.sum(axis=0).astype(np.float32)

    means = np.nanmean(x, axis=0).astype(np.float32)
    stds = np.nanstd(x, axis=0, ddof=1).astype(np.float32)

    bad_std = (~np.isfinite(stds)) | (stds <= 1e-12)

    z = (x - means) / stds
    z[~finite] = 0.0
    z[:, bad_std] = 0.0

    z = z.astype(np.float32, copy=False)
    valid_float = finite.astype(np.float32, copy=False)

    return z, valid_float, valid_counts


def top_k_from_corr_block(
    corr_block: np.ndarray,
    overlap_block: np.ndarray,
    block_start: int,
    tickers: list[str],
    top_k: int,
    min_overlap: int,
    min_abs_corr: float,
    positive_only: bool,
    as_of_date: str,
    window: int,
    valid_coverage: np.ndarray,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    n_block, n_total = corr_block.shape

    for local_i in range(n_block):
        ticker_idx = block_start + local_i

        corr = corr_block[local_i].copy()
        overlap = overlap_block[local_i].copy()

        corr[ticker_idx] = np.nan

        bad = ~np.isfinite(corr)
        bad |= overlap < min_overlap

        if positive_only:
            bad |= corr <= 0

        if min_abs_corr > 0:
            bad |= np.abs(corr) < min_abs_corr

        corr[bad] = np.nan

        finite_idx = np.flatnonzero(np.isfinite(corr))

        if finite_idx.size == 0:
            continue

        k = min(top_k, finite_idx.size)

        # Sort only finite candidates. For top positive correlation, descending corr.
        candidate_corr = corr[finite_idx]
        order = np.argsort(candidate_corr)[::-1][:k]
        peer_indices = finite_idx[order]

        for rank, peer_idx in enumerate(peer_indices, start=1):
            rows.append(
                {
                    "as_of_date": as_of_date,
                    "window": int(window),
                    "ticker": tickers[ticker_idx],
                    "peer_rank": int(rank),
                    "peer": tickers[peer_idx],
                    "corr": float(corr[peer_idx]),
                    "overlap": int(overlap[peer_idx]),
                    "ticker_valid_coverage": float(valid_coverage[ticker_idx]),
                    "peer_valid_coverage": float(valid_coverage[peer_idx]),
                }
            )

    return rows


def compute_top_peers(
    returns: np.ndarray,
    tickers: list[str],
    dates: list[str],
    *,
    window: int,
    top_k: int,
    min_overlap: int,
    block_size: int,
    min_abs_corr: float,
    positive_only: bool,
) -> pd.DataFrame:
    if window <= 1:
        raise ValueError("--window must be greater than 1.")

    if top_k <= 0:
        raise ValueError("--top-k must be positive.")

    if block_size <= 0:
        raise ValueError("--block-size must be positive.")

    if returns.shape[0] < window:
        raise ValueError(
            f"Returns matrix has only {returns.shape[0]} rows, but window={window}."
        )

    if len(tickers) != returns.shape[1]:
        raise RuntimeError(
            f"Ticker count mismatch: {len(tickers)} tickers, {returns.shape[1]} matrix columns."
        )

    window_returns = returns[-window:, :]

    as_of_date = dates[-1]

    print(f"Using trailing window: {window:,} rows")
    print(f"As-of date: {as_of_date}")
    print(f"Tickers: {len(tickers):,}")

    z, valid_float, valid_counts = standardize_window(window_returns)
    valid_coverage = valid_counts / float(window)

    all_rows: list[dict[str, object]] = []

    n = len(tickers)

    started = time.perf_counter()

    for block_start in range(0, n, block_size):
        block_end = min(block_start + block_size, n)

        z_block = z[:, block_start:block_end]
        valid_block = valid_float[:, block_start:block_end]

        # Approximate pairwise correlation using column-standardized returns.
        # Missing values are zeroed after standardization, and overlap is tracked separately.
        numerator = z_block.T @ z
        overlap = valid_block.T @ valid_float

        denom = np.maximum(overlap - 1.0, 1.0)
        corr_block = numerator / denom

        rows = top_k_from_corr_block(
            corr_block=corr_block,
            overlap_block=overlap,
            block_start=block_start,
            tickers=tickers,
            top_k=top_k,
            min_overlap=min_overlap,
            min_abs_corr=min_abs_corr,
            positive_only=positive_only,
            as_of_date=as_of_date,
            window=window,
            valid_coverage=valid_coverage,
        )

        all_rows.extend(rows)

        elapsed = time.perf_counter() - started
        print(
            f"Processed tickers {block_start:,}–{block_end - 1:,} "
            f"({block_end:,}/{n:,}) in {elapsed:.2f}s"
        )

    peers = pd.DataFrame(all_rows)

    if not peers.empty:
        peers = peers.sort_values(
            ["ticker", "peer_rank"],
            ascending=[True, True],
        ).reset_index(drop=True)

    return peers


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
