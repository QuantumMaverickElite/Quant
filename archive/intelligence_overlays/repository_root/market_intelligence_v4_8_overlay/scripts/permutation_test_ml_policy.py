from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


BASELINE_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)

ML_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_walk_forward_ml_adjusted",
    "allocator_confidence_ml_intelligence_adjusted",
    "allocator_confidence_ml_policy_adjusted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Permutation-test an ML allocator policy against shuffled within-date ML scores."
    )
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--strength", type=float, default=20.0)
    parser.add_argument("--max-abs-delta", type=float, default=0.10)
    parser.add_argument("--min-abs-delta", type=float, default=0.02)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--permutations", type=int, default=1_000)
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--ml-confidence-col")
    return parser.parse_args()


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path}")


def write_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
    elif suffix in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
    else:
        raise ValueError(f"Unsupported file type: {path}")


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


def policy_confidence(base: pd.Series, ml: pd.Series, *, strength: float, cap: float, threshold: float) -> pd.Series:
    base_num = pd.to_numeric(base, errors="coerce")
    ml_num = pd.to_numeric(ml, errors="coerce")
    delta = (ml_num - base_num).fillna(0.0) * float(strength)
    delta = delta.clip(lower=-float(cap), upper=float(cap))
    delta = delta.where(delta.abs().ge(float(threshold)), 0.0)
    return base_num + delta


def deterministic_lift(
    df: pd.DataFrame,
    *,
    date_col: str,
    ticker_col: str,
    baseline_col: str,
    policy_col: str,
    return_col: str,
    top_n: int,
    cash: float,
) -> tuple[float, float, int, float]:
    data = df.copy()
    data["_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data["_return"] = pd.to_numeric(data[return_col], errors="coerce")
    data = data.dropna(subset=["_date", "_return"])
    baseline_returns: list[float] = []
    policy_returns: list[float] = []
    changed = 0
    overlaps: list[float] = []
    for _, day in data.groupby("_date", sort=True):
        baseline = day.sort_values(baseline_col, ascending=False).drop_duplicates(ticker_col).head(top_n)
        policy = day.sort_values(policy_col, ascending=False).drop_duplicates(ticker_col).head(top_n)
        b_tickers = set(baseline[ticker_col].astype(str))
        p_tickers = set(policy[ticker_col].astype(str))
        changed += int(b_tickers != p_tickers)
        overlaps.append(len(b_tickers & p_tickers) / max(1, int(top_n)))
        baseline_returns.append(float(baseline["_return"].mean()) if len(baseline) else 0.0)
        policy_returns.append(float(policy["_return"].mean()) if len(policy) else 0.0)
    if not baseline_returns:
        return np.nan, np.nan, 0, np.nan
    b = np.asarray(baseline_returns, dtype=float)
    p = np.asarray(policy_returns, dtype=float)
    b_end = cash * np.cumprod(1.0 + b)[-1]
    p_end = cash * np.cumprod(1.0 + p)[-1]
    return float(p_end - b_end), float(np.nanmean(p - b)), changed, float(np.nanmean(overlaps))


def shuffle_ml_within_date(df: pd.DataFrame, *, date_col: str, ml_col: str, rng: np.random.Generator) -> pd.Series:
    out = pd.Series(index=df.index, dtype=float)
    dates = pd.to_datetime(df[date_col], errors="coerce")
    ml = pd.to_numeric(df[ml_col], errors="coerce")
    for _, idx in dates.groupby(dates).groups.items():
        values = ml.loc[idx].to_numpy(dtype=float, copy=True)
        rng.shuffle(values)
        out.loc[idx] = values
    return out


def write_plots(summary: pd.DataFrame, simulations: pd.DataFrame, out_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable; skipped plots: {exc}")
        return
    plots = out_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    top = summary.sort_values("true_lift_minus_null_p95", ascending=False).head(20)
    labels = [f"{r.return_col} top{int(r.top_n)}" for r in top.itertuples(index=False)]
    plt.figure(figsize=(11, max(5, 0.35 * len(top))))
    plt.barh(labels[::-1], top["true_lift_minus_null_p95"].iloc[::-1])
    plt.axvline(0, color="black", linewidth=1.0)
    plt.title("True Lift Minus Shuffled-Null p95")
    plt.xlabel("cash lift over null p95")
    plt.tight_layout()
    plt.savefig(plots / "true_lift_minus_null_p95.png", dpi=150)
    plt.close()

    if not simulations.empty:
        focus = summary.sort_values("true_lift", ascending=False).head(1)
        if not focus.empty:
            row = focus.iloc[0]
            sims = simulations[
                simulations["return_col"].eq(row["return_col"]) & simulations["top_n"].eq(int(row["top_n"]))
            ]
            plt.figure(figsize=(10, 5))
            plt.hist(sims["permuted_lift"], bins=50, alpha=0.75, color="tab:blue")
            plt.axvline(float(row["true_lift"]), color="tab:red", linewidth=2.0, label="true lift")
            plt.title(f"Permutation Null ({row['return_col']}, top {int(row['top_n'])})")
            plt.xlabel("cash policy lift under shuffled ML scores")
            plt.ylabel("count")
            plt.legend()
            plt.tight_layout()
            plt.savefig(plots / "best_policy_permutation_null.png", dpi=150)
            plt.close()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = read_table(args.predictions).copy()
    ticker_col = detect_ticker_col(df, args.ticker_col)
    date_col = detect_date_col(df, args.date_col)
    base_col = detect_col(df, args.baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline confidence")
    ml_col = detect_col(df, args.ml_confidence_col, ML_CONFIDENCE_CANDIDATES, "ML confidence")
    rng = np.random.default_rng(args.seed)

    policy_col = "_true_policy_confidence"
    df[policy_col] = policy_confidence(
        df[base_col],
        df[ml_col],
        strength=float(args.strength),
        cap=float(args.max_abs_delta),
        threshold=float(args.min_abs_delta),
    )

    summary_rows: list[dict] = []
    sim_rows: list[dict] = []
    for return_col in args.return_cols:
        if return_col not in df.columns:
            continue
        for top_n in args.top_ns:
            true_lift, true_mean_lift, changed, overlap = deterministic_lift(
                df,
                date_col=date_col,
                ticker_col=ticker_col,
                baseline_col=base_col,
                policy_col=policy_col,
                return_col=return_col,
                top_n=int(top_n),
                cash=float(args.cash),
            )
            permuted: list[float] = []
            for i in range(int(args.permutations)):
                shuffled_col = "_shuffled_ml_confidence"
                shuffled_policy_col = "_shuffled_policy_confidence"
                df[shuffled_col] = shuffle_ml_within_date(df, date_col=date_col, ml_col=ml_col, rng=rng)
                df[shuffled_policy_col] = policy_confidence(
                    df[base_col],
                    df[shuffled_col],
                    strength=float(args.strength),
                    cap=float(args.max_abs_delta),
                    threshold=float(args.min_abs_delta),
                )
                lift, _, _, _ = deterministic_lift(
                    df,
                    date_col=date_col,
                    ticker_col=ticker_col,
                    baseline_col=base_col,
                    policy_col=shuffled_policy_col,
                    return_col=return_col,
                    top_n=int(top_n),
                    cash=float(args.cash),
                )
                permuted.append(lift)
                sim_rows.append(
                    {
                        "return_col": return_col,
                        "top_n": int(top_n),
                        "permutation": i,
                        "permuted_lift": lift,
                    }
                )
            null = np.asarray(permuted, dtype=float)
            p_value = (float((null >= true_lift).sum()) + 1.0) / (len(null) + 1.0)
            summary_rows.append(
                {
                    "return_col": return_col,
                    "top_n": int(top_n),
                    "true_lift": true_lift,
                    "true_mean_return_lift": true_mean_lift,
                    "changed_windows": changed,
                    "avg_overlap": overlap,
                    "null_lift_p05": float(np.nanquantile(null, 0.05)),
                    "null_lift_p50": float(np.nanquantile(null, 0.50)),
                    "null_lift_p95": float(np.nanquantile(null, 0.95)),
                    "true_lift_minus_null_p95": float(true_lift - np.nanquantile(null, 0.95)),
                    "permutation_p_value": p_value,
                    "permutations": int(args.permutations),
                    "strength": float(args.strength),
                    "max_abs_delta": float(args.max_abs_delta),
                    "min_abs_delta": float(args.min_abs_delta),
                }
            )

    summary = pd.DataFrame(summary_rows).sort_values("true_lift_minus_null_p95", ascending=False)
    simulations = pd.DataFrame(sim_rows)
    write_table(summary, args.out_dir / "ml_policy_permutation_summary.csv")
    write_table(simulations, args.out_dir / "ml_policy_permutation_simulations.csv")
    write_plots(summary, simulations, args.out_dir)

    print(f"Predictions: {args.predictions}")
    print(f"Saved permutation summary: {args.out_dir / 'ml_policy_permutation_summary.csv'}")
    display = [
        "return_col",
        "top_n",
        "true_lift",
        "null_lift_p50",
        "null_lift_p95",
        "true_lift_minus_null_p95",
        "permutation_p_value",
        "changed_windows",
        "avg_overlap",
    ]
    print(summary[[c for c in display if c in summary.columns]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
