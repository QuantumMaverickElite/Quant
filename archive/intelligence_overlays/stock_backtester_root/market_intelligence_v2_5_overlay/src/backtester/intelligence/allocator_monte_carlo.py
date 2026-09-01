from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .allocator_diagnostics import dedupe_by_ticker, evaluated_rows
from .candidates import read_table


@dataclass(slots=True)
class MonteCarloResult:
    summary: pd.DataFrame
    simulations: pd.DataFrame


def _first_existing(df: pd.DataFrame, cols: list[str]) -> str | None:
    return next((col for col in cols if col in df.columns), None)


def infer_drawdown_col(df: pd.DataFrame, return_col: str, drawdown_col: str | None) -> str | None:
    if drawdown_col and drawdown_col in df.columns:
        return drawdown_col
    if return_col.startswith("next_") and return_col.endswith("_return"):
        candidate = f"max_drawdown_{return_col.removesuffix('_return')}"
        if candidate in df.columns:
            return candidate
    return None


def portfolio_stats(df: pd.DataFrame, *, return_col: str, drawdown_col: str | None) -> dict[str, float]:
    stats = {
        "mean_return": float(df[return_col].mean()),
        "median_return": float(df[return_col].median()),
        "hit_rate": float(df[return_col].gt(0).mean()),
        "count": float(len(df)),
    }
    if drawdown_col and drawdown_col in df.columns:
        stats["avg_drawdown"] = float(df[drawdown_col].mean())
        stats["worst_drawdown"] = float(df[drawdown_col].min())
    return stats


def select_portfolios(
    df: pd.DataFrame,
    *,
    top_n: int,
    return_col: str,
    unique_tickers: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
    pre_col = _first_existing(
        df,
        ["allocator_confidence_pre_intelligence", "adjusted_confidence"],
    )
    post_col = _first_existing(
        df,
        ["allocator_confidence_intelligence_adjusted", "adjusted_confidence_intelligence_adjusted"],
    )
    if pre_col is None or post_col is None:
        raise ValueError("Could not find pre/post allocator confidence columns")

    clean = df.dropna(subset=[return_col]).copy()
    pre_universe = dedupe_by_ticker(clean, score_col=pre_col) if unique_tickers else clean
    post_universe = dedupe_by_ticker(clean, score_col=post_col) if unique_tickers else clean
    pre = pre_universe.sort_values(pre_col, ascending=False).head(top_n)
    post = post_universe.sort_values(post_col, ascending=False).head(top_n)
    return pre, post, pre_col, post_col


def bootstrap_selected(
    *,
    pre: pd.DataFrame,
    post: pd.DataFrame,
    return_col: str,
    drawdown_col: str | None,
    iterations: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows: list[dict] = []
    pre_returns = pre[return_col].to_numpy(dtype=float)
    post_returns = post[return_col].to_numpy(dtype=float)
    pre_drawdowns = pre[drawdown_col].to_numpy(dtype=float) if drawdown_col else None
    post_drawdowns = post[drawdown_col].to_numpy(dtype=float) if drawdown_col else None
    n_pre = len(pre_returns)
    n_post = len(post_returns)

    for i in range(iterations):
        pre_idx = rng.integers(0, n_pre, n_pre)
        post_idx = rng.integers(0, n_post, n_post)
        row = {
            "iteration": i,
            "sim_type": "bootstrap_selected",
            "pre_return": float(np.nanmean(pre_returns[pre_idx])),
            "post_return": float(np.nanmean(post_returns[post_idx])),
        }
        row["post_minus_pre"] = row["post_return"] - row["pre_return"]
        if pre_drawdowns is not None and post_drawdowns is not None:
            row["pre_avg_drawdown"] = float(np.nanmean(pre_drawdowns[pre_idx]))
            row["post_avg_drawdown"] = float(np.nanmean(post_drawdowns[post_idx]))
            row["drawdown_delta"] = row["post_avg_drawdown"] - row["pre_avg_drawdown"]
        rows.append(row)
    return pd.DataFrame(rows)


def random_portfolios(
    *,
    universe: pd.DataFrame,
    pre: pd.DataFrame,
    post: pd.DataFrame,
    return_col: str,
    drawdown_col: str | None,
    top_n: int,
    iterations: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows: list[dict] = []
    n = min(top_n, len(universe))
    returns = universe[return_col].to_numpy(dtype=float)
    drawdowns = universe[drawdown_col].to_numpy(dtype=float) if drawdown_col else None
    pre_mean = float(pre[return_col].mean())
    post_mean = float(post[return_col].mean())

    for i in range(iterations):
        idx = rng.choice(len(universe), size=n, replace=False)
        random_return = float(np.nanmean(returns[idx]))
        row = {
            "iteration": i,
            "sim_type": "random_portfolio",
            "random_return": random_return,
            "pre_excess_vs_random": pre_mean - random_return,
            "post_excess_vs_random": post_mean - random_return,
        }
        if drawdowns is not None:
            row["random_avg_drawdown"] = float(np.nanmean(drawdowns[idx]))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_simulations(
    *,
    pre: pd.DataFrame,
    post: pd.DataFrame,
    universe: pd.DataFrame,
    simulations: pd.DataFrame,
    return_col: str,
    drawdown_col: str | None,
    top_n: int,
) -> pd.DataFrame:
    pre_stats = portfolio_stats(pre, return_col=return_col, drawdown_col=drawdown_col)
    post_stats = portfolio_stats(post, return_col=return_col, drawdown_col=drawdown_col)
    universe_stats = portfolio_stats(universe, return_col=return_col, drawdown_col=drawdown_col)

    boot = simulations[simulations["sim_type"].eq("bootstrap_selected")]
    rand = simulations[simulations["sim_type"].eq("random_portfolio")]

    rows = [
        {
            "metric": "deterministic_pre_return",
            "value": pre_stats["mean_return"],
            "top_n": top_n,
        },
        {
            "metric": "deterministic_post_return",
            "value": post_stats["mean_return"],
            "top_n": top_n,
        },
        {
            "metric": "deterministic_post_minus_pre",
            "value": post_stats["mean_return"] - pre_stats["mean_return"],
            "top_n": top_n,
        },
        {
            "metric": "universe_mean_return",
            "value": universe_stats["mean_return"],
            "top_n": top_n,
        },
        {
            "metric": "bootstrap_prob_post_beats_pre",
            "value": float(boot["post_minus_pre"].gt(0).mean()) if len(boot) else np.nan,
            "top_n": top_n,
        },
        {
            "metric": "bootstrap_lift_p05",
            "value": float(boot["post_minus_pre"].quantile(0.05)) if len(boot) else np.nan,
            "top_n": top_n,
        },
        {
            "metric": "bootstrap_lift_p50",
            "value": float(boot["post_minus_pre"].quantile(0.50)) if len(boot) else np.nan,
            "top_n": top_n,
        },
        {
            "metric": "bootstrap_lift_p95",
            "value": float(boot["post_minus_pre"].quantile(0.95)) if len(boot) else np.nan,
            "top_n": top_n,
        },
        {
            "metric": "random_prob_pre_beats_random",
            "value": float(rand["pre_excess_vs_random"].gt(0).mean()) if len(rand) else np.nan,
            "top_n": top_n,
        },
        {
            "metric": "random_prob_post_beats_random",
            "value": float(rand["post_excess_vs_random"].gt(0).mean()) if len(rand) else np.nan,
            "top_n": top_n,
        },
    ]

    if drawdown_col:
        rows.extend(
            [
                {
                    "metric": "deterministic_pre_avg_drawdown",
                    "value": pre_stats.get("avg_drawdown", np.nan),
                    "top_n": top_n,
                },
                {
                    "metric": "deterministic_post_avg_drawdown",
                    "value": post_stats.get("avg_drawdown", np.nan),
                    "top_n": top_n,
                },
                {
                    "metric": "deterministic_drawdown_delta",
                    "value": post_stats.get("avg_drawdown", np.nan) - pre_stats.get("avg_drawdown", np.nan),
                    "top_n": top_n,
                },
                {
                    "metric": "bootstrap_prob_post_drawdown_better",
                    "value": float(boot["drawdown_delta"].gt(0).mean()) if "drawdown_delta" in boot else np.nan,
                    "top_n": top_n,
                },
            ]
        )
    return pd.DataFrame(rows)


def run_allocator_monte_carlo(
    *,
    signals_path: str | Path,
    return_col: str,
    top_n: int,
    iterations: int = 10000,
    seed: int = 7,
    drawdown_col: str | None = None,
    unique_tickers: bool = True,
) -> MonteCarloResult:
    df = evaluated_rows(read_table(signals_path))
    if return_col not in df.columns:
        raise ValueError(f"Return column not found: {return_col}")
    drawdown = infer_drawdown_col(df, return_col, drawdown_col)

    pre, post, _, post_col = select_portfolios(
        df,
        top_n=top_n,
        return_col=return_col,
        unique_tickers=unique_tickers,
    )
    universe = df.dropna(subset=[return_col]).copy()
    if unique_tickers:
        universe = dedupe_by_ticker(universe, score_col=post_col)

    rng = np.random.default_rng(seed)
    boot = bootstrap_selected(
        pre=pre,
        post=post,
        return_col=return_col,
        drawdown_col=drawdown,
        iterations=iterations,
        rng=rng,
    )
    rand = random_portfolios(
        universe=universe,
        pre=pre,
        post=post,
        return_col=return_col,
        drawdown_col=drawdown,
        top_n=top_n,
        iterations=iterations,
        rng=rng,
    )
    simulations = pd.concat([boot, rand], ignore_index=True, sort=False)
    summary = summarize_simulations(
        pre=pre,
        post=post,
        universe=universe,
        simulations=simulations,
        return_col=return_col,
        drawdown_col=drawdown,
        top_n=top_n,
    )
    return MonteCarloResult(summary=summary, simulations=simulations)
