# src/backtester/correlation/features.py

from __future__ import annotations

from typing import Any

import numpy as np


def window_corr_matrix(
    returns_window: Any,
    xp: Any,
    eps: float = 1e-12,
) -> Any:
    """
    Compute a correlation matrix for one return window.

    returns_window:
        Shape (W, N)

    Returns:
        Shape (N, N)
    """

    if returns_window.ndim != 2:
        raise ValueError("returns_window must be 2D with shape (W, N).")

    w = returns_window.shape[0]

    if w < 2:
        raise ValueError("returns_window must contain at least 2 rows.")

    x = returns_window.astype(xp.float32, copy=False)

    mean = xp.nanmean(x, axis=0, keepdims=True)
    centered = x - mean

    std = xp.nanstd(centered, axis=0, ddof=1, keepdims=True)
    standardized = centered / xp.maximum(std, eps)

    corr = (standardized.T @ standardized) / max(w - 1, 1)
    corr = xp.clip(corr, -1.0, 1.0)

    return corr


def average_corr_to_group(
    corr: Any,
    group_codes: Any,
    xp: Any,
    exclude_self: bool = True,
) -> Any:
    """
    For each asset, compute average correlation to assets in the same group.

    corr:
        Shape (N, N)

    group_codes:
        Shape (N,), integer group labels. Missing groups should be -1.

    Returns:
        Shape (N,)
    """

    n = corr.shape[0]
    out = xp.full(n, xp.nan, dtype=xp.float32)

    unique_groups = xp.unique(group_codes)

    for group in unique_groups.tolist():
        if int(group) < 0:
            continue

        idx = xp.where(group_codes == group)[0]

        if idx.size <= 1:
            continue

        sub = corr[idx[:, None], idx[None, :]]

        if exclude_self:
            mask = ~xp.eye(idx.size, dtype=bool)
            vals = xp.where(mask, sub, xp.nan)
        else:
            vals = sub

        out[idx] = xp.nanmean(vals, axis=1)

    return out


def average_corr_to_market(corr: Any, xp: Any) -> Any:
    """
    For each asset, compute average correlation to all other assets.
    """

    n = corr.shape[0]

    if n <= 1:
        return xp.full(n, xp.nan, dtype=xp.float32)

    mask = ~xp.eye(n, dtype=bool)
    vals = xp.where(mask, corr, xp.nan)

    return xp.nanmean(vals, axis=1)


def top_k_peers(
    corr: Any,
    xp: Any,
    k: int = 5,
) -> tuple[Any, Any]:
    """
    Find top-k correlated peers for each asset.

    Returns:
        peer_indices: Shape (N, k)
        peer_corrs:   Shape (N, k)
    """

    if k <= 0:
        raise ValueError("k must be positive.")

    n = corr.shape[0]

    if n <= 1:
        peer_indices = xp.full((n, k), -1, dtype=xp.int32)
        peer_corrs = xp.full((n, k), xp.nan, dtype=xp.float32)
        return peer_indices, peer_corrs

    safe_corr = corr.copy()
    diag = xp.arange(n)
    safe_corr[diag, diag] = -xp.inf

    actual_k = min(k, n - 1)

    unsorted_idx = xp.argpartition(-safe_corr, kth=actual_k - 1, axis=1)[:, :actual_k]

    unsorted_vals = xp.take_along_axis(safe_corr, unsorted_idx, axis=1)
    order = xp.argsort(-unsorted_vals, axis=1)

    peer_indices = xp.take_along_axis(unsorted_idx, order, axis=1)
    peer_corrs = xp.take_along_axis(unsorted_vals, order, axis=1)

    if actual_k < k:
        pad_width = k - actual_k
        peer_indices = xp.concatenate(
            [peer_indices, xp.full((n, pad_width), -1, dtype=xp.int32)],
            axis=1,
        )
        peer_corrs = xp.concatenate(
            [peer_corrs, xp.full((n, pad_width), xp.nan, dtype=xp.float32)],
            axis=1,
        )

    return peer_indices.astype(xp.int32), peer_corrs.astype(xp.float32)


def to_numpy(arr: Any) -> np.ndarray:
    """
    Move NumPy/CuPy array back to NumPy.
    """

    if hasattr(arr, "get"):
        return arr.get()

    return np.asarray(arr)
