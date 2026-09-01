from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score ML policy candidates against validation and permutation gates.")
    parser.add_argument("--validation", type=Path, help="ml_policy_candidate_validation.csv")
    parser.add_argument(
        "--permutation",
        nargs="*",
        default=[],
        help="One or more ml_policy_permutation_summary.csv files. Use label=path to force the period label.",
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--min-periods", type=int, default=2)
    parser.add_argument("--max-p-value", type=float, default=0.05)
    parser.add_argument("--require-positive-p05", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")
    return pd.read_csv(path)


def parse_labeled_path(value: str) -> tuple[str | None, Path]:
    if "=" not in value:
        return None, Path(value)
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise SystemExit(f"Invalid labeled path: {value}")
    return label, Path(raw_path.strip())


def infer_period_from_path(path: Path) -> str:
    parts = list(path.parts)
    aliases = {
        "stress_2022_2023_ml_sentiment": "2022_2023",
        "sec_news_massive_full_pool": "2025_2026",
        "sec_news_grid_20260623": "2025_2026",
    }
    for token in reversed(parts):
        if token in aliases:
            return aliases[token]
    return path.parent.name


def normalize_validation(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "period" not in out.columns:
        out["period"] = "validation"
    rename = {
        "deterministic_policy_minus_baseline": "validation_lift",
        "policy_minus_baseline_p05": "validation_p05",
        "policy_minus_baseline_p50": "validation_p50",
        "policy_minus_baseline_p95": "validation_p95",
        "prob_policy_beats_baseline": "validation_prob_beats",
        "prob_policy_nonworse_baseline": "validation_prob_nonworse",
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    keep = [
        "period",
        "return_col",
        "top_n",
        "validation_lift",
        "validation_p05",
        "validation_p50",
        "validation_p95",
        "validation_prob_beats",
        "validation_prob_nonworse",
        "changed_windows",
        "avg_overlap",
    ]
    return out[[c for c in keep if c in out.columns]].copy()


def normalize_permutation(path: Path, period_label: str | None = None) -> pd.DataFrame:
    df = read_csv(path).copy()
    df["period"] = period_label or infer_period_from_path(path)
    rename = {
        "true_lift": "permutation_true_lift",
        "null_lift_p50": "permutation_null_p50",
        "null_lift_p95": "permutation_null_p95",
        "true_lift_minus_null_p95": "permutation_true_minus_null_p95",
        "permutation_p_value": "permutation_p_value",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    keep = [
        "period",
        "return_col",
        "top_n",
        "permutation_true_lift",
        "permutation_null_p50",
        "permutation_null_p95",
        "permutation_true_minus_null_p95",
        "permutation_p_value",
    ]
    return df[[c for c in keep if c in df.columns]].copy()


def score_rows(df: pd.DataFrame, *, max_p_value: float, require_positive_p05: bool) -> pd.DataFrame:
    out = df.copy()
    out["validation_lift_pass"] = pd.to_numeric(out.get("validation_lift"), errors="coerce").fillna(-1).gt(0)
    out["validation_p05_pass"] = pd.to_numeric(out.get("validation_p05"), errors="coerce").fillna(-1).ge(0)
    out["permutation_p_value_pass"] = pd.to_numeric(out.get("permutation_p_value"), errors="coerce").fillna(1).le(max_p_value)
    out["permutation_null_pass"] = pd.to_numeric(out.get("permutation_true_minus_null_p95"), errors="coerce").fillna(-1).gt(0)
    row_pass = out["validation_lift_pass"] & out["permutation_p_value_pass"] & out["permutation_null_pass"]
    if require_positive_p05:
        row_pass = row_pass & out["validation_p05_pass"]
    out["row_gate_pass"] = row_pass
    return out


def summarize_candidate_gates(df: pd.DataFrame, *, min_periods: int) -> pd.DataFrame:
    rows: list[dict] = []
    for (return_col, top_n), group in df.groupby(["return_col", "top_n"], dropna=False):
        periods = int(group["period"].nunique())
        passed_periods = int(group[group["row_gate_pass"]]["period"].nunique())
        rows.append(
            {
                "return_col": return_col,
                "top_n": int(top_n),
                "periods": periods,
                "passed_periods": passed_periods,
                "candidate_gate_pass": passed_periods >= int(min_periods),
                "mean_validation_lift": float(pd.to_numeric(group["validation_lift"], errors="coerce").mean()),
                "min_validation_p05": float(pd.to_numeric(group.get("validation_p05"), errors="coerce").min()),
                "max_permutation_p_value": float(pd.to_numeric(group.get("permutation_p_value"), errors="coerce").max()),
                "min_true_minus_null_p95": float(pd.to_numeric(group.get("permutation_true_minus_null_p95"), errors="coerce").min()),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["candidate_gate_pass", "passed_periods", "mean_validation_lift"], ascending=False)
    return out


def main() -> None:
    args = parse_args()
    frames: list[pd.DataFrame] = []
    if args.validation:
        frames.append(normalize_validation(read_csv(args.validation)))
    if not frames:
        raise SystemExit("Provide --validation.")
    validation = pd.concat(frames, ignore_index=True)

    if args.permutation:
        permutation_frames: list[pd.DataFrame] = []
        for value in args.permutation:
            period_label, path = parse_labeled_path(value)
            permutation_frames.append(normalize_permutation(path, period_label=period_label))
        permutation = pd.concat(permutation_frames, ignore_index=True)
        merged = validation.merge(permutation, on=["period", "return_col", "top_n"], how="left")
    else:
        merged = validation.copy()

    scored = score_rows(merged, max_p_value=args.max_p_value, require_positive_p05=args.require_positive_p05)
    summary = summarize_candidate_gates(scored, min_periods=args.min_periods)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.out, index=False)
    summary_path = args.out.with_name(args.out.stem + "_summary.csv")
    summary.to_csv(summary_path, index=False)

    print(f"Saved row gate scores: {args.out}")
    print(f"Saved candidate gate summary: {summary_path}")
    if not summary.empty:
        print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
