from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtester.utils.tables import read_table, write_table
from .ml_policy_common import detect_col, detect_date_col, detect_ticker_col


BASELINE_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)

ML_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_walk_forward_ml_adjusted",
    "allocator_confidence_ml_intelligence_adjusted",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a controlled ML policy-strength adjustment to allocator signals.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--audit-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--strength", type=float, default=20.0)
    parser.add_argument("--max-abs-delta", type=float, default=0.05)
    parser.add_argument("--min-abs-delta", type=float, default=0.0)
    parser.add_argument("--output-confidence-col", default="allocator_confidence_ml_policy_adjusted")
    parser.add_argument("--ticker-col")
    parser.add_argument("--date-col")
    parser.add_argument("--baseline-confidence-col")
    parser.add_argument("--ml-confidence-col")
    parser.add_argument("--top-ns", nargs="+", type=int, default=[5, 10, 20, 30, 40, 50])
    parser.add_argument("--return-cols", nargs="+", default=["next_5d_return", "next_10d_return"])
    parser.add_argument("--cash", type=float, default=10_000.0)
    return parser.parse_args()


def apply_policy(
    df: pd.DataFrame,
    *,
    base_col: str,
    ml_col: str,
    output_col: str,
    strength: float,
    max_abs_delta: float,
    min_abs_delta: float,
) -> pd.DataFrame:
    out = df.copy()
    base = pd.to_numeric(out[base_col], errors="coerce")
    ml = pd.to_numeric(out[ml_col], errors="coerce")
    raw_delta = (ml - base).fillna(0.0)
    scaled_delta = raw_delta * float(strength)
    capped_delta = scaled_delta.clip(lower=-float(max_abs_delta), upper=float(max_abs_delta))
    thresholded_delta = capped_delta.where(capped_delta.abs().ge(float(min_abs_delta)), 0.0)
    out["ml_policy_raw_delta"] = raw_delta
    out["ml_policy_scaled_delta"] = scaled_delta
    out["ml_policy_capped_delta"] = capped_delta
    out["ml_policy_thresholded_delta"] = thresholded_delta
    out["ml_policy_delta_was_capped"] = (scaled_delta - capped_delta).abs() > 1e-12
    out["ml_policy_delta_was_thresholded"] = (capped_delta.abs() > 0) & (thresholded_delta.abs() <= 1e-12)
    out[output_col] = base + thresholded_delta
    return out


def top_sets(day: pd.DataFrame, *, ticker_col: str, baseline_col: str, policy_col: str, top_n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = day.sort_values(baseline_col, ascending=False).drop_duplicates(ticker_col).head(top_n).copy()
    policy = day.sort_values(policy_col, ascending=False).drop_duplicates(ticker_col).head(top_n).copy()
    return baseline, policy


def build_audit(
    df: pd.DataFrame,
    *,
    ticker_col: str,
    date_col: str,
    baseline_col: str,
    policy_col: str,
    top_ns: list[int],
    return_cols: list[str],
    cash: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()
    data["_policy_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=["_policy_date"])
    audit_rows: list[dict] = []
    summary_rows: list[dict] = []

    available_returns = [col for col in return_cols if col in data.columns]
    for top_n in top_ns:
        per_date_rows: list[dict] = []
        for date_value, day in data.groupby("_policy_date", sort=True):
            baseline, policy = top_sets(
                day,
                ticker_col=ticker_col,
                baseline_col=baseline_col,
                policy_col=policy_col,
                top_n=int(top_n),
            )
            b_tickers = set(baseline[ticker_col].astype(str))
            p_tickers = set(policy[ticker_col].astype(str))
            entered = sorted(p_tickers - b_tickers)
            dropped = sorted(b_tickers - p_tickers)
            overlap = len(b_tickers & p_tickers) / max(1, int(top_n))
            for ticker in entered:
                row = day[day[ticker_col].astype(str).eq(ticker)].sort_values(policy_col, ascending=False).iloc[0]
                audit_rows.append(
                    {
                        "date": date_value,
                        "top_n": int(top_n),
                        "action": "entered",
                        "ticker": ticker,
                        "baseline_confidence": row.get(baseline_col),
                        "policy_confidence": row.get(policy_col),
                        "ml_policy_capped_delta": row.get("ml_policy_capped_delta"),
                        "ml_policy_thresholded_delta": row.get("ml_policy_thresholded_delta"),
                        "ml_policy_delta_was_capped": row.get("ml_policy_delta_was_capped"),
                        "ml_policy_delta_was_thresholded": row.get("ml_policy_delta_was_thresholded"),
                        **{col: row.get(col) for col in available_returns},
                    }
                )
            for ticker in dropped:
                row = day[day[ticker_col].astype(str).eq(ticker)].sort_values(baseline_col, ascending=False).iloc[0]
                audit_rows.append(
                    {
                        "date": date_value,
                        "top_n": int(top_n),
                        "action": "dropped",
                        "ticker": ticker,
                        "baseline_confidence": row.get(baseline_col),
                        "policy_confidence": row.get(policy_col),
                        "ml_policy_capped_delta": row.get("ml_policy_capped_delta"),
                        "ml_policy_thresholded_delta": row.get("ml_policy_thresholded_delta"),
                        "ml_policy_delta_was_capped": row.get("ml_policy_delta_was_capped"),
                        "ml_policy_delta_was_thresholded": row.get("ml_policy_delta_was_thresholded"),
                        **{col: row.get(col) for col in available_returns},
                    }
                )

            date_row = {"date": date_value, "top_n": int(top_n), "overlap": overlap, "changed": float(bool(entered or dropped))}
            for return_col in available_returns:
                b_ret = pd.to_numeric(baseline[return_col], errors="coerce").mean()
                p_ret = pd.to_numeric(policy[return_col], errors="coerce").mean()
                date_row[f"baseline_{return_col}"] = b_ret
                date_row[f"policy_{return_col}"] = p_ret
                date_row[f"policy_minus_baseline_{return_col}"] = p_ret - b_ret
            per_date_rows.append(date_row)

        per_date = pd.DataFrame(per_date_rows)
        if per_date.empty:
            continue
        row = {
            "top_n": int(top_n),
            "dates": int(len(per_date)),
            "changed_windows": int(per_date["changed"].sum()),
            "avg_overlap": float(per_date["overlap"].mean()),
        }
        for return_col in available_returns:
            lift_col = f"policy_minus_baseline_{return_col}"
            row[f"mean_policy_minus_baseline_{return_col}"] = float(per_date[lift_col].mean())
            row[f"cash_policy_minus_baseline_{return_col}"] = float(cash * per_date[lift_col].mean())
            row[f"deterministic_policy_minus_baseline_{return_col}"] = deterministic_lift(
                per_date[f"baseline_{return_col}"], per_date[f"policy_{return_col}"], cash=cash
            )
        summary_rows.append(row)

    return pd.DataFrame(audit_rows), pd.DataFrame(summary_rows)


def deterministic_lift(baseline_returns: pd.Series, policy_returns: pd.Series, *, cash: float) -> float:
    b = pd.to_numeric(baseline_returns, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    p = pd.to_numeric(policy_returns, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(b) == 0:
        return np.nan
    return float(cash * np.cumprod(1.0 + p)[-1] - cash * np.cumprod(1.0 + b)[-1])


def main() -> None:
    args = parse_args()
    df = read_table(args.signals)
    ticker_col = detect_ticker_col(df, args.ticker_col)
    date_col = detect_date_col(df, args.date_col)
    base_col = detect_col(df, args.baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline confidence")
    ml_col = detect_col(df, args.ml_confidence_col, ML_CONFIDENCE_CANDIDATES, "ML confidence")

    out = apply_policy(
        df,
        base_col=base_col,
        ml_col=ml_col,
        output_col=args.output_confidence_col,
        strength=args.strength,
        max_abs_delta=args.max_abs_delta,
        min_abs_delta=args.min_abs_delta,
    )
    write_table(out, args.out)

    audit, summary = build_audit(
        out,
        ticker_col=ticker_col,
        date_col=date_col,
        baseline_col=base_col,
        policy_col=args.output_confidence_col,
        top_ns=[int(v) for v in args.top_ns],
        return_cols=args.return_cols,
        cash=float(args.cash),
    )
    audit_out = args.audit_out or args.out.with_name(args.out.stem + "_policy_audit.csv")
    summary_out = args.summary_out or args.out.with_name(args.out.stem + "_policy_summary.csv")
    write_table(audit, audit_out)
    write_table(summary, summary_out)

    print(f"Saved ML-policy-adjusted signals: {args.out}")
    print(f"Saved policy audit: {audit_out}")
    print(f"Saved policy summary: {summary_out}")
    print(f"Baseline column: {base_col}")
    print(f"ML column: {ml_col}")
    print(f"Output confidence column: {args.output_confidence_col}")
    if not summary.empty:
        print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
