from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

BackendName = Literal["numpy", "cupy"]


def get_array_module(backend: BackendName = "numpy"):
    """
    GPU-ready backend selector.

    For now, NumPy is the default and safest backend.
    CuPy support is optional and only used if installed.
    """
    if backend == "numpy":
        return np

    if backend == "cupy":
        try:
            import cupy as cp

            return cp
        except ImportError as exc:
            raise ImportError(
                "CuPy is not installed. Install cupy-cuda12x or use backend='numpy'."
            ) from exc

    raise ValueError(f"Unsupported backend: {backend}")


@dataclass(frozen=True)
class MarketMatrices:
    tickers: list[str]
    price_dates: pd.DatetimeIndex
    check_indices: np.ndarray
    returns: np.ndarray
    scores: np.ndarray


@dataclass(frozen=True)
class MatrixSimulationConfig:
    capital: float = 10_000.0
    sample_size: int = 24
    portfolio_size: int = 8
    max_weight: float = 0.35
    seed: int = 42
    backend: BackendName = "numpy"


@dataclass(frozen=True)
class ThresholdPolicyConfig:
    thresholds: tuple[float, ...] = (
        0.00,
        0.01,
        0.03,
        0.05,
        0.075,
        0.10,
        0.15,
        0.20,
    )


def load_feature_matrix(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str)

    if "adjusted_score" not in df.columns:
        raise ValueError("Feature matrix must contain adjusted_score.")

    df["adjusted_score"] = pd.to_numeric(
        df["adjusted_score"],
        errors="coerce",
    ).fillna(0.0)

    return df.sort_values(["date", "ticker"]).reset_index(drop=True)


def load_price_matrix(path: str) -> pd.DataFrame:
    prices = pd.read_csv(path)

    first_col = prices.columns[0]
    prices[first_col] = pd.to_datetime(prices[first_col])

    prices = prices.rename(columns={first_col: "date"})
    prices = prices.set_index("date").sort_index()

    for col in prices.columns:
        prices[col] = pd.to_numeric(prices[col], errors="coerce")

    return prices


def prepare_market_matrices(
    features: pd.DataFrame,
    prices: pd.DataFrame,
) -> MarketMatrices:
    """
    Convert feature/prices DataFrames into aligned matrix form.

    This is the bridge from Pandas research data to fast NumPy/CuPy engines.
    """
    tickers = sorted(set(features["ticker"]).intersection(prices.columns))

    if not tickers:
        raise ValueError("No overlapping tickers between features and prices.")

    features = features[features["ticker"].isin(tickers)].copy()
    prices = prices[tickers].copy()

    score_df = (
        features.pivot_table(
            index="date",
            columns="ticker",
            values="adjusted_score",
            aggfunc="last",
        )
        .reindex(columns=tickers)
        .sort_index()
        .fillna(0.0)
    )

    start = score_df.index.min()
    end = score_df.index.max()

    prices = prices[(prices.index >= start) & (prices.index <= end)].copy()
    prices = prices.ffill().bfill()

    returns_df = prices.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)

    score_dates = score_df.index
    price_dates = prices.index

    check_indices: list[int] = []
    valid_score_rows: list[int] = []

    for i, date in enumerate(score_dates):
        pos = price_dates.searchsorted(date)

        if pos < len(price_dates) and price_dates[pos] == date:
            check_indices.append(pos)
            valid_score_rows.append(i)
        elif pos > 0:
            check_indices.append(pos - 1)
            valid_score_rows.append(i)

    if not check_indices:
        raise ValueError("No check dates align with price dates.")

    return MarketMatrices(
        tickers=tickers,
        price_dates=price_dates,
        check_indices=np.asarray(check_indices, dtype=np.int64),
        returns=returns_df.to_numpy(dtype=float),
        scores=score_df.iloc[valid_score_rows].to_numpy(dtype=float),
    )


def generate_run_samples(
    n_runs: int,
    n_tickers: int,
    sample_size: int,
    seed: int,
) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    size = min(sample_size, n_tickers)

    return [
        np.sort(rng.choice(n_tickers, size=size, replace=False)).astype(np.int64)
        for _ in range(n_runs)
    ]


def max_drawdown(equity: np.ndarray) -> float:
    running_max = np.maximum.accumulate(equity)
    drawdown = equity / running_max - 1.0
    return float(np.min(drawdown) * 100.0)


def sharpe_ratio(equity: np.ndarray) -> float:
    if equity.size < 2:
        return 0.0

    returns = equity[1:] / equity[:-1] - 1.0
    std = np.std(returns)

    if std == 0 or not np.isfinite(std):
        return 0.0

    return float((np.mean(returns) / std) * np.sqrt(252))


def cagr(equity: np.ndarray, dates: pd.DatetimeIndex) -> float:
    start = float(equity[0])
    end = float(equity[-1])

    if start <= 0:
        return 0.0

    days = max((dates[-1] - dates[0]).days, 1)
    years = days / 365.25

    return float(((end / start) ** (1.0 / years) - 1.0) * 100.0)


def summarize_equity(
    equity: np.ndarray,
    dates: pd.DatetimeIndex,
    capital: float,
) -> dict[str, float]:
    final_equity = float(equity[-1])
    total_return_pct = (final_equity / capital - 1.0) * 100.0

    return {
        "final_equity": final_equity,
        "total_return_pct": float(total_return_pct),
        "cagr_pct": cagr(equity, dates),
        "max_drawdown_pct": max_drawdown(equity),
        "sharpe": sharpe_ratio(equity),
    }


def build_top_n_weights(
    scores: np.ndarray,
    sample_indices: np.ndarray,
    portfolio_size: int,
    max_weight: float,
    n_tickers: int,
) -> np.ndarray:
    """
    Basic allocator policy: top-N equal-weight by score.

    This is intentionally simple. It is not the final allocator.
    Future allocator policies should plug in at this layer.
    """
    if sample_indices.size == 0:
        return np.zeros(n_tickers, dtype=float)

    sample_scores = scores[sample_indices]
    n_hold = min(portfolio_size, sample_indices.size)

    top_local = np.argpartition(-sample_scores, kth=n_hold - 1)[:n_hold]
    top_indices = sample_indices[top_local]

    top_scores = scores[top_indices]
    order = np.argsort(-top_scores)
    top_indices = top_indices[order]

    weight = min(1.0 / n_hold, max_weight)

    weights = np.zeros(n_tickers, dtype=float)
    weights[top_indices] = weight

    return weights


def average_score_for_weights(scores: np.ndarray, weights: np.ndarray) -> float:
    holding_indices = np.flatnonzero(weights > 0)

    if holding_indices.size == 0:
        return 0.0

    return float(np.mean(scores[holding_indices]))


def average_score_for_positions(
    scores: np.ndarray, position_values: np.ndarray
) -> float:
    holding_indices = np.flatnonzero(position_values > 0)

    if holding_indices.size == 0:
        return 0.0

    return float(np.mean(scores[holding_indices]))


def turnover_pct(old_weights: np.ndarray, new_weights: np.ndarray) -> float:
    return float(np.sum(np.abs(new_weights - old_weights)) / 2.0 * 100.0)


@dataclass(frozen=True)
class MatrixBacktestResult:
    equity: np.ndarray
    n_rebalances: float
    mean_turnover_pct: float


def run_threshold_backtest(
    matrices: MarketMatrices,
    sample_indices: np.ndarray,
    threshold: float,
    portfolio_size: int,
    max_weight: float,
    capital: float,
) -> MatrixBacktestResult:
    """
    Drift-corrected threshold rebalance backtest.

    This function tracks position values between rebalance dates, so holdings
    drift naturally with returns. Target weights are only reset when a rebalance
    is triggered.
    """
    returns = matrices.returns
    scores = matrices.scores
    check_indices = matrices.check_indices

    n_days, n_tickers = returns.shape

    equity = np.empty(n_days, dtype=float)
    equity[0] = capital

    position_values = np.zeros(n_tickers, dtype=float)
    cash = capital

    check_lookup = {
        int(day_idx): score_row_idx
        for score_row_idx, day_idx in enumerate(check_indices)
    }

    n_rebalances = 0
    turnovers: list[float] = []

    def current_equity() -> float:
        return float(cash + np.sum(position_values))

    def current_weights() -> np.ndarray:
        total = current_equity()
        if total <= 0:
            return np.zeros(n_tickers, dtype=float)
        return position_values / total

    def apply_rebalance(new_weights: np.ndarray) -> None:
        nonlocal position_values, cash

        total = current_equity()
        invested_weight = float(np.sum(new_weights))

        position_values = total * new_weights
        cash = max(total * (1.0 - invested_weight), 0.0)

    if 0 in check_lookup:
        score_row = scores[check_lookup[0]]
        initial_weights = build_top_n_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        turnovers.append(100.0)
        apply_rebalance(initial_weights)
        n_rebalances += 1
        equity[0] = current_equity()

    for day in range(1, n_days):
        position_values *= 1.0 + returns[day]
        equity[day] = current_equity()

        if day not in check_lookup:
            continue

        score_row = scores[check_lookup[day]]

        candidate_weights = build_top_n_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        current_score = average_score_for_positions(score_row, position_values)
        candidate_score = average_score_for_weights(score_row, candidate_weights)
        improvement = candidate_score - current_score

        has_positions = np.count_nonzero(position_values > 0) > 0

        if not has_positions or improvement >= threshold:
            live_weights = current_weights()
            turnovers.append(turnover_pct(live_weights, candidate_weights))
            apply_rebalance(candidate_weights)
            n_rebalances += 1
            equity[day] = current_equity()

    return MatrixBacktestResult(
        equity=equity,
        n_rebalances=float(n_rebalances),
        mean_turnover_pct=float(np.mean(turnovers)) if turnovers else 0.0,
    )


def run_threshold_grid_for_sample(
    matrices: MarketMatrices,
    sample_indices: np.ndarray,
    thresholds: np.ndarray,
    portfolio_size: int,
    max_weight: float,
    capital: float,
) -> list[dict[str, float]]:
    """
    Run one sampled universe across many thresholds.

    This is the engine-side version of the threshold sweep. It returns metrics
    only, not curves. Curves can be added later as an optional output mode.
    """
    rows: list[dict[str, float]] = []

    for threshold in thresholds:
        result = run_threshold_backtest(
            matrices=matrices,
            sample_indices=sample_indices,
            threshold=float(threshold),
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            capital=capital,
        )

        metrics = summarize_equity(
            equity=result.equity,
            dates=matrices.price_dates,
            capital=capital,
        )

        rows.append(
            {
                "threshold": float(threshold),
                **metrics,
                "n_rebalances": result.n_rebalances,
                "mean_turnover_pct": result.mean_turnover_pct,
            }
        )

    return rows


def summarize_threshold_trials(trials: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for threshold, group in trials.groupby("threshold"):
        rows.append(
            {
                "threshold": threshold,
                "mean_return_pct": group["total_return_pct"].mean(),
                "median_return_pct": group["total_return_pct"].median(),
                "mean_cagr_pct": group["cagr_pct"].mean(),
                "mean_sharpe": group["sharpe"].mean(),
                "median_sharpe": group["sharpe"].median(),
                "mean_max_drawdown_pct": group["max_drawdown_pct"].mean(),
                "prob_loss_pct": float((group["total_return_pct"] < 0).mean() * 100.0),
                "prob_sharpe_below_1_pct": float((group["sharpe"] < 1).mean() * 100.0),
                "mean_rebalances": group["n_rebalances"].mean(),
                "median_rebalances": group["n_rebalances"].median(),
                "mean_turnover_pct": group["mean_turnover_pct"].mean(),
            }
        )

    return pd.DataFrame(rows).sort_values("threshold")


@dataclass(frozen=True)
class MatrixThresholdGridResult:
    rows: list[dict[str, float]]
    curves: list[pd.DataFrame]


def run_batched_threshold_grid_for_sample(
    matrices: MarketMatrices,
    sample_indices: np.ndarray,
    thresholds: np.ndarray,
    portfolio_size: int,
    max_weight: float,
    capital: float,
    run_id: int = 1,
    save_curves: bool = False,
) -> MatrixThresholdGridResult:
    """
    Fast drift-corrected threshold grid for one sampled universe.

    This is the engine-side equivalent of the v3 batched threshold logic:
    one run sample is simulated across all thresholds at the same time.

    It is still NumPy-first, but the shape is GPU-ready:
    - equity: thresholds x days
    - position_values: thresholds x tickers
    - threshold decisions are vectorized across threshold policies
    """
    returns = matrices.returns
    scores = matrices.scores
    check_indices = matrices.check_indices
    price_dates = matrices.price_dates

    n_days, n_tickers = returns.shape
    thresholds = np.asarray(thresholds, dtype=float)
    n_thresholds = thresholds.size

    equity = np.empty((n_thresholds, n_days), dtype=float)
    equity[:, 0] = capital

    position_values = np.zeros((n_thresholds, n_tickers), dtype=float)
    cash = np.full(n_thresholds, capital, dtype=float)

    n_rebalances = np.zeros(n_thresholds, dtype=float)
    turnover_sums = np.zeros(n_thresholds, dtype=float)
    turnover_counts = np.zeros(n_thresholds, dtype=float)

    check_lookup = {
        int(day_idx): score_row_idx
        for score_row_idx, day_idx in enumerate(check_indices)
    }

    def current_equity_vec() -> np.ndarray:
        return cash + position_values.sum(axis=1)

    def current_weights_matrix() -> np.ndarray:
        totals = current_equity_vec()
        out = np.zeros_like(position_values)
        valid = totals > 0

        if np.any(valid):
            out[valid] = position_values[valid] / totals[valid, None]

        return out

    def apply_rebalance(mask: np.ndarray, new_weights: np.ndarray) -> None:
        nonlocal position_values, cash

        if not np.any(mask):
            return

        totals = current_equity_vec()
        invested_weight = float(np.sum(new_weights))

        position_values[mask] = totals[mask, None] * new_weights[None, :]
        cash[mask] = np.maximum(totals[mask] * (1.0 - invested_weight), 0.0)

    if 0 in check_lookup:
        score_row = scores[check_lookup[0]]

        initial_weights = build_top_n_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        all_mask = np.ones(n_thresholds, dtype=bool)
        apply_rebalance(all_mask, initial_weights)

        n_rebalances += 1.0
        turnover_sums += 100.0
        turnover_counts += 1.0
        equity[:, 0] = current_equity_vec()

    for day in range(1, n_days):
        position_values *= 1.0 + returns[day][None, :]
        equity[:, day] = current_equity_vec()

        if day not in check_lookup:
            continue

        score_row = scores[check_lookup[day]]

        candidate_weights = build_top_n_weights(
            scores=score_row,
            sample_indices=sample_indices,
            portfolio_size=portfolio_size,
            max_weight=max_weight,
            n_tickers=n_tickers,
        )

        candidate_score = average_score_for_weights(score_row, candidate_weights)

        current_scores = np.array(
            [
                average_score_for_positions(score_row, position_values[i])
                for i in range(n_thresholds)
            ],
            dtype=float,
        )

        improvements = candidate_score - current_scores
        has_positions = (position_values > 0).any(axis=1)

        rebalance_mask = (~has_positions) | (improvements >= thresholds)

        if np.any(rebalance_mask):
            live_weights = current_weights_matrix()

            turnovers = np.array(
                [
                    turnover_pct(live_weights[i], candidate_weights)
                    for i in range(n_thresholds)
                ],
                dtype=float,
            )

            turnover_sums[rebalance_mask] += turnovers[rebalance_mask]
            turnover_counts[rebalance_mask] += 1.0
            n_rebalances[rebalance_mask] += 1.0

            apply_rebalance(rebalance_mask, candidate_weights)
            equity[:, day] = current_equity_vec()

    rows: list[dict[str, float]] = []
    curves: list[pd.DataFrame] = []

    for threshold_idx, threshold in enumerate(thresholds):
        eq = equity[threshold_idx]

        metrics = summarize_equity(
            equity=eq,
            dates=price_dates,
            capital=capital,
        )

        mean_turnover = (
            turnover_sums[threshold_idx] / turnover_counts[threshold_idx]
            if turnover_counts[threshold_idx] > 0
            else 0.0
        )

        rows.append(
            {
                "threshold": float(threshold),
                **metrics,
                "n_rebalances": float(n_rebalances[threshold_idx]),
                "mean_turnover_pct": float(mean_turnover),
            }
        )

        if save_curves:
            curves.append(
                pd.DataFrame(
                    {
                        "date": price_dates,
                        "equity": eq,
                        "threshold": float(threshold),
                        "run_id": run_id,
                    }
                )
            )

    return MatrixThresholdGridResult(rows=rows, curves=curves)
