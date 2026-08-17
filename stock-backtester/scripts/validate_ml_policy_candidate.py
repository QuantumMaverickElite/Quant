from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtester.utils.tables import read_table, write_table


BASELINE_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)

ML_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_ml_policy_adjusted",
    "allocator_confidence_walk_forward_ml_adjusted",
    "allocator_confidence_ml_intelligence_adjusted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate one ML policy candidate across prediction files.")
    parser.add_argument("--predictions", nargs="+", required=True, help="Either path or label=path.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--strength", type=float, default=20.0)
    parser.add_argument("--max-abs-delta", type=float, default=0.10)
    parser.add_argument("--min-abs-delta", type=float, default=0.02)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--focus-return-col", default="next_10d_return")
    parser.add_argument("--focus-top-n", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument("--block-size", type=int, default=3)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--ml-confidence-col")
    return parser.parse_args()


def parse_prediction_arg(value: str) -> tuple[str, Path]:
    if "=" in value:
        label, path = value.split("=", 1)
        return label.strip(), Path(path)
    path = Path(value)
    return path.stem, path


def detect_col(df: pd.DataFrame, requested: str | None, candidates: tuple[str, ...], label: str) -> str:
    if requested:
        if requested not in df.columns:
            raise ValueError(f"{label} column not found: {requested}")
        return requested
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Could not detect {label} column. Tried: {', '.join(candidates)}")


def detect_ticker_col(df: pd.DataFrame, requested: str | None) -> str:
    return detect_col(df, requested, ("ticker", "query", "symbol"), "ticker")


def detect_date_col(df: pd.DataFrame, requested: str | None) -> str:
    return detect_col(df, requested, ("date", "signal_date", "as_of", "timestamp"), "date")


def apply_policy(df: pd.DataFrame, *, base_col: str, ml_col: str, strength: float, cap: float, threshold: float) -> pd.Series:
    base = pd.to_numeric(df[base_col], errors="coerce")
    ml = pd.to_numeric(df[ml_col], errors="coerce")
    delta = (ml - base).fillna(0.0) * float(strength)
    delta = delta.clip(lower=-float(cap), upper=float(cap))
    delta = delta.where(delta.abs().ge(float(threshold)), 0.0)
    return base + delta


def max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return np.nan
    peak = np.maximum.accumulate(equity)
    return float(np.nanmin(equity / peak - 1.0))


def bootstrap_indices(rng: np.random.Generator, n_steps: int, iterations: int, block_size: int) -> np.ndarray:
    if block_size <= 1:
        return rng.integers(0, n_steps, size=(iterations, n_steps))
    starts = rng.integers(0, n_steps, size=(iterations, int(np.ceil(n_steps / block_size))))
    out = np.empty((iterations, n_steps), dtype=int)
    for i, row in enumerate(starts):
        idx: list[int] = []
        for start in row:
            idx.extend(((start + np.arange(block_size)) % n_steps).tolist())
        out[i, :] = np.asarray(idx[:n_steps], dtype=int)
    return out


def per_date_returns(
    df: pd.DataFrame,
    *,
    ticker_col: str,
    date_col: str,
    baseline_col: str,
    policy_col: str,
    return_col: str,
    top_n: int,
) -> pd.DataFrame:
    data = df.copy()
    data["_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data["_return"] = pd.to_numeric(data[return_col], errors="coerce")
    data = data.dropna(subset=["_date", "_return"])
    rows: list[dict] = []
    for date_value, day in data.groupby("_date", sort=True):
        baseline = day.sort_values(baseline_col, ascending=False).drop_duplicates(ticker_col).head(top_n)
        policy = day.sort_values(policy_col, ascending=False).drop_duplicates(ticker_col).head(top_n)
        b_tickers = set(baseline[ticker_col].astype(str))
        p_tickers = set(policy[ticker_col].astype(str))
        rows.append(
            {
                "date": date_value,
                "baseline_return": float(baseline["_return"].mean()) if len(baseline) else np.nan,
                "policy_return": float(policy["_return"].mean()) if len(policy) else np.nan,
                "overlap": len(b_tickers & p_tickers) / max(1, int(top_n)),
                "changed": float(b_tickers != p_tickers),
            }
        )
    return pd.DataFrame(rows)


def summarize_returns(
    returns: pd.DataFrame,
    *,
    cash: float,
    iterations: int,
    block_size: int,
    rng: np.random.Generator,
) -> dict:
    if returns.empty:
        return {}
    b = pd.to_numeric(returns["baseline_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    p = pd.to_numeric(returns["policy_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    b_eq = cash * np.cumprod(1.0 + b)
    p_eq = cash * np.cumprod(1.0 + p)
    idx = bootstrap_indices(rng, n_steps=len(returns), iterations=iterations, block_size=block_size)
    b_paths = cash * np.cumprod(1.0 + b[idx], axis=1)
    p_paths = cash * np.cumprod(1.0 + p[idx], axis=1)
    diff = p_paths[:, -1] - b_paths[:, -1]
    b_dd = np.array([max_drawdown(path) for path in b_paths])
    p_dd = np.array([max_drawdown(path) for path in p_paths])
    return {
        "test_windows": int(len(returns)),
        "changed_windows": int(pd.to_numeric(returns["changed"], errors="coerce").sum()),
        "avg_overlap": float(returns["overlap"].mean()),
        "baseline_ending_equity": float(b_eq[-1]),
        "policy_ending_equity": float(p_eq[-1]),
        "deterministic_policy_minus_baseline": float(p_eq[-1] - b_eq[-1]),
        "baseline_total_return": float(b_eq[-1] / cash - 1.0),
        "policy_total_return": float(p_eq[-1] / cash - 1.0),
        "baseline_max_drawdown": max_drawdown(b_eq),
        "policy_max_drawdown": max_drawdown(p_eq),
        "prob_policy_beats_baseline": float((diff > 0).mean()),
        "prob_policy_nonworse_baseline": float((diff >= -1e-12).mean()),
        "prob_policy_drawdown_better_baseline": float((p_dd > b_dd).mean()),
        "policy_minus_baseline_p05": float(np.quantile(diff, 0.05)),
        "policy_minus_baseline_p50": float(np.quantile(diff, 0.50)),
        "policy_minus_baseline_p95": float(np.quantile(diff, 0.95)),
    }


def write_plots(summary: pd.DataFrame, out_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable; skipped plots: {exc}")
        return
    plots = out_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    focus = summary.sort_values("deterministic_policy_minus_baseline", ascending=False).head(30)
    labels = [f"{r.period} {r.return_col} top{int(r.top_n)}" for r in focus.itertuples(index=False)]
    plt.figure(figsize=(11, max(5, 0.35 * len(focus))))
    plt.barh(labels[::-1], focus["deterministic_policy_minus_baseline"].iloc[::-1])
    plt.axvline(0, color="black", linewidth=1.0)
    plt.title("ML Policy Candidate Lift Across Periods")
    plt.xlabel("deterministic cash policy minus baseline")
    plt.tight_layout()
    plt.savefig(plots / "policy_candidate_lift_by_period.png", dpi=150)
    plt.close()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    rows: list[dict] = []

    for label, path in [parse_prediction_arg(value) for value in args.predictions]:
        if not path.exists():
            print(f"Skipping missing predictions: {path}")
            continue
        df = read_table(path).copy()
        ticker_col = detect_ticker_col(df, args.ticker_col)
        date_col = detect_date_col(df, args.date_col)
        base_col = detect_col(df, args.baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline confidence")
        ml_col = detect_col(df, args.ml_confidence_col, ML_CONFIDENCE_CANDIDATES, "ML confidence")
        policy_col = "_candidate_policy_confidence"
        df[policy_col] = apply_policy(
            df,
            base_col=base_col,
            ml_col=ml_col,
            strength=args.strength,
            cap=args.max_abs_delta,
            threshold=args.min_abs_delta,
        )
        for return_col in args.return_cols:
            if return_col not in df.columns:
                continue
            for top_n in args.top_ns:
                returns = per_date_returns(
                    df,
                    ticker_col=ticker_col,
                    date_col=date_col,
                    baseline_col=base_col,
                    policy_col=policy_col,
                    return_col=return_col,
                    top_n=int(top_n),
                )
                summary = summarize_returns(
                    returns,
                    cash=float(args.cash),
                    iterations=int(args.iterations),
                    block_size=int(args.block_size),
                    rng=rng,
                )
                if not summary:
                    continue
                summary.update(
                    {
                        "period": label,
                        "predictions": str(path),
                        "return_col": return_col,
                        "top_n": int(top_n),
                        "strength": float(args.strength),
                        "max_abs_delta": float(args.max_abs_delta),
                        "min_abs_delta": float(args.min_abs_delta),
                        "baseline_col": base_col,
                        "ml_col": ml_col,
                    }
                )
                rows.append(summary)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["period", "return_col", "top_n"])
    write_table(out, args.out_dir / "ml_policy_candidate_validation.csv")
    write_plots(out, args.out_dir)

    focus = out[out["return_col"].eq(args.focus_return_col) & out["top_n"].eq(int(args.focus_top_n))].copy()
    if not focus.empty:
        focus = focus.sort_values("deterministic_policy_minus_baseline", ascending=False)
        write_table(focus, args.out_dir / f"focus_{args.focus_return_col}_top{args.focus_top_n}.csv")

    print(f"Saved validation summary: {args.out_dir / 'ml_policy_candidate_validation.csv'}")
    display = [
        "period",
        "return_col",
        "top_n",
        "deterministic_policy_minus_baseline",
        "prob_policy_beats_baseline",
        "prob_policy_nonworse_baseline",
        "policy_minus_baseline_p05",
        "policy_minus_baseline_p50",
        "policy_minus_baseline_p95",
        "changed_windows",
        "avg_overlap",
    ]
    if not out.empty:
        print(out[[c for c in display if c in out.columns]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
