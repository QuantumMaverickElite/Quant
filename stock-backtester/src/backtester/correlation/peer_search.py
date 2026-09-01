"""Staged cached-matrix peer search implementation."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd


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
