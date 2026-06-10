from __future__ import annotations

from typing import Any


from backtester.engines.array_backend import ArrayBackend


def compute_return_matrix(
    prices: Any,
    backend: ArrayBackend,
) -> Any:
    """
    Compute simple daily returns from a price matrix.

    Input shape:
        dates x tickers

    Output shape:
        (dates - 1) x tickers
    """
    xp = backend.xp
    prices = backend.asarray(prices, dtype=xp.float32)

    returns = prices[1:] / prices[:-1] - 1.0
    returns = xp.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

    # Safety for benchmark/prototype use. Real strategy modules can choose
    # whether to apply return clipping before calling batch ops.
    return xp.clip(returns, -0.25, 0.25)


def cross_sectional_rank_desc(
    scores: Any,
    backend: ArrayBackend,
) -> Any:
    """
    Rank scores cross-sectionally, highest score = rank 0.

    Input shape:
        dates x tickers

    Output shape:
        dates x tickers

    This uses stable sorting so tied scores are deterministic.
    Lower ticker index wins ties.
    """
    xp = backend.xp
    scores = backend.asarray(scores, dtype=xp.float32)

    # argsort is stable for numpy when kind="stable".
    # CuPy supports stable=True in newer versions less consistently,
    # so we use lexsort for deterministic tie-breaking.
    n_tickers = scores.shape[1]
    ticker_ids = xp.arange(n_tickers)

    ranks = xp.empty_like(scores, dtype=xp.int32)

    for row_idx in range(scores.shape[0]):
        # NumPy accepts a tuple of keys. CuPy expects an array-like key matrix.
        # Key order: primary key is -score, secondary tie-break is ticker id.
        keys = xp.stack((ticker_ids, -scores[row_idx]), axis=0)
        order = xp.lexsort(keys)
        ranks[row_idx, order] = xp.arange(n_tickers, dtype=xp.int32)

    return ranks


def top_n_mask_from_scores(
    scores: Any,
    n: int,
    backend: ArrayBackend,
) -> Any:
    """
    Build a deterministic top-N mask from scores.

    Input shape:
        dates x tickers

    Output shape:
        dates x tickers, bool

    This is the fast path used by batch evaluators. It avoids the slow
    row-by-row lexsort loop by adding a tiny deterministic tie-break penalty
    based on ticker index, then sorting the full matrix along axis=1.

    Tie break:
    1. Higher score first.
    2. Lower ticker index first.
    """
    xp = backend.xp
    scores = backend.asarray(scores, dtype=xp.float32)

    n_dates, n_tickers = scores.shape
    n_hold = min(int(n), int(n_tickers))

    if n_hold <= 0:
        return xp.zeros_like(scores, dtype=bool)

    ticker_ids = xp.arange(n_tickers, dtype=xp.float32)

    # Tiny tie-break penalty. For equal scores, lower ticker id has a slightly
    # higher adjusted score. The penalty is intentionally tiny relative to
    # normal score scale, but enough to make exact ties deterministic.
    tie_penalty = ticker_ids * xp.float32(1e-12)
    adjusted_scores = scores - tie_penalty[None, :]

    order = xp.argsort(-adjusted_scores, axis=1)
    top_indices = order[:, :n_hold]

    mask = xp.zeros_like(scores, dtype=bool)
    rows = xp.arange(n_dates)[:, None]
    mask[rows, top_indices] = True

    return mask


def equal_weight_from_mask(
    mask: Any,
    backend: ArrayBackend,
    max_weight: float | None = None,
) -> Any:
    """
    Convert a boolean holding mask into equal weights.

    Input shape:
        dates x tickers

    Output shape:
        dates x tickers
    """
    xp = backend.xp
    mask = backend.asarray(mask).astype(xp.float32)

    counts = mask.sum(axis=1, keepdims=True)
    counts = xp.maximum(counts, 1.0)

    weights = mask / counts

    if max_weight is not None:
        weights = xp.minimum(weights, float(max_weight))

        # Renormalize after max-weight clipping if total weight is positive.
        totals = weights.sum(axis=1, keepdims=True)
        weights = xp.where(totals > 0, weights / totals, weights)

    return weights


def portfolio_returns_from_weights(
    weights: Any,
    returns: Any,
    backend: ArrayBackend,
) -> Any:
    """
    Compute portfolio returns from date x ticker weights and returns.

    Both inputs should have compatible shape:
        dates x tickers

    Output shape:
        dates
    """
    xp = backend.xp
    weights = backend.asarray(weights, dtype=xp.float32)
    returns = backend.asarray(returns, dtype=xp.float32)

    return xp.sum(weights * returns, axis=1)


def equity_curve_from_returns(
    portfolio_returns: Any,
    backend: ArrayBackend,
    capital: float = 10_000.0,
) -> Any:
    """
    Convert portfolio returns into an equity curve.

    Input shape:
        dates

    Output shape:
        dates + 1
    """
    xp = backend.xp
    portfolio_returns = backend.asarray(portfolio_returns, dtype=xp.float32)

    growth = xp.cumprod(1.0 + portfolio_returns)
    equity = xp.empty(portfolio_returns.shape[0] + 1, dtype=xp.float32)
    equity[0] = float(capital)
    equity[1:] = float(capital) * growth

    return equity
