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

HEURISTIC_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_intelligence_adjusted",
    "adjusted_confidence_intelligence_adjusted",
)

ML_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_walk_forward_ml_adjusted",
    "allocator_confidence_ml_intelligence_adjusted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep ML confidence adjustment strength without retraining."
    )
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 15, 20, 30, 40, 50])
    parser.add_argument("--strengths", nargs="+", type=float, default=[0.5, 1, 2, 3, 5, 10, 15, 20])
    parser.add_argument("--max-abs-deltas", nargs="+", default=["none", "0.01", "0.02", "0.05", "0.10"])
    parser.add_argument("--min-abs-deltas", nargs="+", default=["0", "0.005", "0.01", "0.02"])
    parser.add_argument("--cash", type=float, default=10_000.0)
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument("--block-size", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--spaghetti-paths", type=int, default=250)
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--heuristic-confidence-col")
    parser.add_argument("--ml-confidence-col")
    parser.add_argument("--focus-return-col", default="next_10d_return")
    parser.add_argument("--focus-top-n", type=int, default=10)
    return parser.parse_args()


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


def parse_cap(value: str) -> float | None:
    text = str(value).strip().lower()
    if text in {"none", "nan", "null", ""}:
        return None
    out = float(text)
    if out <= 0:
        return None
    return out


def cap_label(value: float | None) -> str:
    if value is None:
        return "none"
    return str(value).replace(".", "p")


def adjusted_confidence(
    base: pd.Series,
    ml: pd.Series,
    *,
    strength: float,
    max_abs_delta: float | None,
    min_abs_delta: float,
) -> pd.Series:
    delta = pd.to_numeric(ml, errors="coerce").fillna(pd.to_numeric(base, errors="coerce")) - pd.to_numeric(
        base, errors="coerce"
    )
    scaled = delta * float(strength)
    if max_abs_delta is not None:
        scaled = scaled.clip(lower=-float(max_abs_delta), upper=float(max_abs_delta))
    if min_abs_delta > 0:
        scaled = scaled.where(scaled.abs().ge(float(min_abs_delta)), 0.0)
    return pd.to_numeric(base, errors="coerce") + scaled


def drawdown_col(df: pd.DataFrame, return_col: str) -> str | None:
    if return_col.startswith("next_") and return_col.endswith("_return"):
        horizon = return_col.removeprefix("next_").removesuffix("_return")
        candidate = f"max_drawdown_next_{horizon}"
        if candidate in df.columns:
            return candidate
    for candidate in ("max_drawdown_next_10d", "max_drawdown_next_20d", "max_drawdown_next_5d"):
        if candidate in df.columns:
            return candidate
    return None


def max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return np.nan
    peak = np.maximum.accumulate(equity)
    return float(np.nanmin(equity / peak - 1.0))


def per_date_returns(
    df: pd.DataFrame,
    *,
    date_col: str,
    ticker_col: str,
    return_col: str,
    top_n: int,
    baseline_col: str,
    adjusted_col: str,
) -> pd.DataFrame:
    dd_col = drawdown_col(df, return_col)
    rows: list[dict] = []
    data = df.copy()
    data["_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data["_return"] = pd.to_numeric(data[return_col], errors="coerce")
    data = data.dropna(subset=["_date", "_return"])

    for date_value, day in data.groupby("_date", sort=True):
        baseline = day.sort_values(baseline_col, ascending=False).drop_duplicates(ticker_col).head(top_n).copy()
        adjusted = day.sort_values(adjusted_col, ascending=False).drop_duplicates(ticker_col).head(top_n).copy()
        b_tickers = set(baseline[ticker_col].astype(str))
        a_tickers = set(adjusted[ticker_col].astype(str))
        row = {
            "date": date_value,
            "baseline_return": float(baseline["_return"].mean()) if len(baseline) else np.nan,
            "ml_return": float(adjusted["_return"].mean()) if len(adjusted) else np.nan,
            "baseline_count": int(len(baseline)),
            "ml_count": int(len(adjusted)),
            "overlap": len(b_tickers & a_tickers) / max(1, int(top_n)),
            "changed": float(b_tickers != a_tickers),
            "entered": ",".join(sorted(a_tickers - b_tickers)),
            "dropped": ",".join(sorted(b_tickers - a_tickers)),
        }
        if dd_col and dd_col in day.columns:
            row["baseline_drawdown"] = float(pd.to_numeric(baseline[dd_col], errors="coerce").mean())
            row["ml_drawdown"] = float(pd.to_numeric(adjusted[dd_col], errors="coerce").mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("date")


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


def summarize_returns(
    returns: pd.DataFrame,
    *,
    cash: float,
    iterations: int,
    block_size: int,
    rng: np.random.Generator,
) -> tuple[dict, pd.DataFrame]:
    n_steps = len(returns)
    if n_steps == 0:
        return {}, pd.DataFrame()
    b = pd.to_numeric(returns["baseline_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    m = pd.to_numeric(returns["ml_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    b_eq = cash * np.cumprod(1.0 + b)
    m_eq = cash * np.cumprod(1.0 + m)

    idx = bootstrap_indices(rng, n_steps=n_steps, iterations=iterations, block_size=block_size)
    b_paths = cash * np.cumprod(1.0 + b[idx], axis=1)
    m_paths = cash * np.cumprod(1.0 + m[idx], axis=1)
    diff = m_paths[:, -1] - b_paths[:, -1]

    b_dd = np.empty(iterations)
    m_dd = np.empty(iterations)
    for i in range(iterations):
        b_dd[i] = max_drawdown(b_paths[i])
        m_dd[i] = max_drawdown(m_paths[i])

    summary = {
        "test_windows": n_steps,
        "baseline_deterministic_ending_equity": float(b_eq[-1]),
        "ml_deterministic_ending_equity": float(m_eq[-1]),
        "deterministic_ml_minus_baseline": float(m_eq[-1] - b_eq[-1]),
        "baseline_deterministic_total_return": float(b_eq[-1] / cash - 1.0),
        "ml_deterministic_total_return": float(m_eq[-1] / cash - 1.0),
        "baseline_deterministic_max_drawdown": max_drawdown(b_eq),
        "ml_deterministic_max_drawdown": max_drawdown(m_eq),
        "avg_overlap": float(returns["overlap"].mean()),
        "changed_windows": int(pd.to_numeric(returns["changed"], errors="coerce").sum()),
        "prob_ml_beats_baseline": float((diff > 0).mean()),
        "prob_ml_nonworse_baseline": float((diff >= -1e-12).mean()),
        "prob_ml_drawdown_better_baseline": float((m_dd > b_dd).mean()),
        "ml_minus_baseline_ending_cash_p05": float(np.quantile(diff, 0.05)),
        "ml_minus_baseline_ending_cash_p50": float(np.quantile(diff, 0.50)),
        "ml_minus_baseline_ending_cash_p95": float(np.quantile(diff, 0.95)),
    }
    sims = pd.DataFrame(
        {
            "iteration": np.arange(iterations, dtype=int),
            "baseline_ending_equity": b_paths[:, -1],
            "ml_ending_equity": m_paths[:, -1],
            "ml_minus_baseline_ending_cash": diff,
            "baseline_max_drawdown": b_dd,
            "ml_max_drawdown": m_dd,
        }
    )
    return summary, sims


def write_best_plots(
    returns: pd.DataFrame,
    sims: pd.DataFrame,
    out_dir: Path,
    *,
    cash: float,
    iterations: int,
    block_size: int,
    seed: int,
    spaghetti_paths: int,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable; skipped plots: {exc}")
        return

    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    b = pd.to_numeric(returns["baseline_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    m = pd.to_numeric(returns["ml_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    det = pd.DataFrame(
        {
            "date": returns["date"],
            "baseline_equity": cash * np.cumprod(1.0 + b),
            "ml_strength_equity": cash * np.cumprod(1.0 + m),
        }
    )
    det.to_csv(out_dir / "best_deterministic_equity.csv", index=False)

    plt.figure(figsize=(11, 6))
    plt.plot(det["date"], det["baseline_equity"], label="baseline")
    plt.plot(det["date"], det["ml_strength_equity"], label="ml strength")
    plt.title("Policy Strength Deterministic Equity")
    plt.xlabel("date")
    plt.ylabel("equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_dir / "policy_strength_deterministic_equity.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.hist(sims["ml_minus_baseline_ending_cash"], bins=50, color="tab:green", alpha=0.75)
    plt.axvline(0, color="black", linewidth=1.0)
    plt.title("Policy Strength ML Minus Baseline Distribution")
    plt.xlabel("ending cash difference")
    plt.ylabel("simulation count")
    plt.tight_layout()
    plt.savefig(plot_dir / "policy_strength_ml_minus_baseline_distribution.png", dpi=150)
    plt.close()

    rng = np.random.default_rng(seed + 997)
    n_steps = len(returns)
    path_count = min(int(spaghetti_paths), int(iterations))
    idx = bootstrap_indices(rng, n_steps=n_steps, iterations=path_count, block_size=block_size)
    b_paths = cash * np.cumprod(1.0 + b[idx], axis=1)
    m_paths = cash * np.cumprod(1.0 + m[idx], axis=1)

    plt.figure(figsize=(11, 6))
    x = np.arange(1, n_steps + 1)
    for i in range(path_count):
        plt.plot(x, b_paths[i], color="tab:blue", alpha=0.08, linewidth=0.8)
        plt.plot(x, m_paths[i], color="tab:green", alpha=0.08, linewidth=0.8)
    plt.plot(x, np.median(b_paths, axis=0), color="tab:blue", linewidth=2.0, label="baseline median")
    plt.plot(x, np.median(m_paths, axis=0), color="tab:green", linewidth=2.0, label="ml strength median")
    plt.title("Policy Strength Bootstrap Equity Spaghetti")
    plt.xlabel("sampled test step")
    plt.ylabel("equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_dir / "policy_strength_bootstrap_spaghetti.png", dpi=150)
    plt.close()


def write_sweep_plots(summary: pd.DataFrame, out_dir: Path, *, focus_return_col: str, focus_top_n: int) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable; skipped plots: {exc}")
        return

    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    focus = summary[
        summary["return_col"].eq(focus_return_col)
        & summary["top_n"].eq(int(focus_top_n))
        & summary["max_abs_delta"].eq("none")
        & summary["min_abs_delta"].eq(0.0)
    ].copy()
    if not focus.empty:
        focus = focus.sort_values("strength")
        plt.figure(figsize=(10, 5))
        plt.plot(focus["strength"], focus["deterministic_ml_minus_baseline"], marker="o", label="deterministic lift")
        plt.plot(focus["strength"], focus["ml_minus_baseline_ending_cash_p50"], marker="o", label="bootstrap median lift")
        plt.axhline(0, color="black", linewidth=1.0)
        plt.title(f"ML Policy Strength Sweep ({focus_return_col}, top {focus_top_n})")
        plt.xlabel("strength")
        plt.ylabel("cash ML minus baseline")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_dir / f"policy_strength_sweep_{focus_return_col}_top{focus_top_n}.png", dpi=150)
        plt.close()

    top = summary.sort_values(
        ["deterministic_ml_minus_baseline", "prob_ml_beats_baseline", "changed_windows"],
        ascending=False,
    ).head(20)
    labels = [
        f"{r.return_col} top{int(r.top_n)} s{r.strength:g} cap{r.max_abs_delta} min{r.min_abs_delta:g}"
        for r in top.itertuples(index=False)
    ]
    plt.figure(figsize=(11, max(5, 0.32 * len(top))))
    plt.barh(labels[::-1], top["deterministic_ml_minus_baseline"].iloc[::-1])
    plt.axvline(0, color="black", linewidth=1.0)
    plt.title("Top Policy Strength Lifts")
    plt.xlabel("deterministic cash ML minus baseline")
    plt.tight_layout()
    plt.savefig(plot_dir / "top_policy_strength_lifts.png", dpi=150)
    plt.close()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = read_table(args.predictions).copy()
    ticker_col = detect_ticker_col(df, args.ticker_col)
    date_col = detect_date_col(df, args.date_col)
    base_col = detect_col(df, args.baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline confidence")
    ml_col = detect_col(df, args.ml_confidence_col, ML_CONFIDENCE_CANDIDATES, "ML confidence")
    heuristic_col = None
    for candidate in ([args.heuristic_confidence_col] if args.heuristic_confidence_col else []) + list(HEURISTIC_CONFIDENCE_CANDIDATES):
        if candidate and candidate in df.columns:
            heuristic_col = candidate
            break

    caps = [parse_cap(value) for value in args.max_abs_deltas]
    min_deltas = [float(value) for value in args.min_abs_deltas]
    rng = np.random.default_rng(args.seed)
    summary_rows: list[dict] = []
    best_payload: tuple[pd.DataFrame, pd.DataFrame, dict] | None = None
    best_score = -np.inf

    for strength in args.strengths:
        for cap in caps:
            for min_delta in min_deltas:
                if cap is not None and min_delta > cap:
                    continue
                adj_col = "_policy_strength_adjusted"
                df[adj_col] = adjusted_confidence(
                    df[base_col],
                    df[ml_col],
                    strength=float(strength),
                    max_abs_delta=cap,
                    min_abs_delta=float(min_delta),
                )
                for return_col in args.return_cols:
                    if return_col not in df.columns:
                        continue
                    for top_n in args.top_ns:
                        returns = per_date_returns(
                            df,
                            date_col=date_col,
                            ticker_col=ticker_col,
                            return_col=return_col,
                            top_n=int(top_n),
                            baseline_col=base_col,
                            adjusted_col=adj_col,
                        )
                        summary, sims = summarize_returns(
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
                                "strength": float(strength),
                                "max_abs_delta": cap_label(cap),
                                "min_abs_delta": float(min_delta),
                                "return_col": return_col,
                                "top_n": int(top_n),
                                "baseline_col": base_col,
                                "heuristic_col": heuristic_col or "",
                                "ml_col": ml_col,
                            }
                        )
                        summary_rows.append(summary)
                        score = summary["deterministic_ml_minus_baseline"]
                        if score > best_score:
                            best_score = score
                            payload_summary = dict(summary)
                            best_payload = (returns.copy(), sims.copy(), payload_summary)

    out = pd.DataFrame(summary_rows)
    if not out.empty:
        out = out.sort_values(
            ["deterministic_ml_minus_baseline", "prob_ml_beats_baseline", "changed_windows"],
            ascending=False,
        )
    write_table(out, args.out_dir / "policy_strength_sweep_summary.csv")
    write_sweep_plots(out, args.out_dir, focus_return_col=args.focus_return_col, focus_top_n=args.focus_top_n)

    if best_payload is not None:
        returns, sims, payload_summary = best_payload
        best_dir = args.out_dir / "best_policy_strength"
        best_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([payload_summary]).to_csv(best_dir / "best_policy_strength_summary.csv", index=False)
        returns.to_csv(best_dir / "best_policy_strength_portfolio_returns.csv", index=False)
        sims.to_csv(best_dir / "best_policy_strength_bootstrap_summary.csv", index=False)
        write_best_plots(
            returns,
            sims,
            best_dir,
            cash=float(args.cash),
            iterations=int(args.iterations),
            block_size=int(args.block_size),
            seed=int(args.seed),
            spaghetti_paths=int(args.spaghetti_paths),
        )

    print(f"Predictions: {args.predictions}")
    print(f"Baseline column: {base_col}")
    print(f"ML column: {ml_col}")
    print(f"Saved sweep summary: {args.out_dir / 'policy_strength_sweep_summary.csv'}")
    if not out.empty:
        display = [
            "return_col",
            "top_n",
            "strength",
            "max_abs_delta",
            "min_abs_delta",
            "deterministic_ml_minus_baseline",
            "prob_ml_beats_baseline",
            "prob_ml_nonworse_baseline",
            "ml_minus_baseline_ending_cash_p05",
            "ml_minus_baseline_ending_cash_p50",
            "ml_minus_baseline_ending_cash_p95",
            "avg_overlap",
            "changed_windows",
        ]
        print(out[[c for c in display if c in out.columns]].head(30).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
