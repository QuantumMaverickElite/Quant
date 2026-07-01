#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".jsonl":
        return pd.read_json(path, lines=True)
    raise ValueError(f"Unsupported table type: {path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--left", required=True, help="First classification run.")
    p.add_argument("--right", required=True, help="Second classification run.")
    p.add_argument("--left-name", default="left")
    p.add_argument("--right-name", default="right")
    p.add_argument(
        "--out",
        default="outputs/intelligence/llm_provider_comparison.csv",
        help="Output comparison CSV.",
    )
    args = p.parse_args()

    left = read_table(args.left)
    right = read_table(args.right)

    required = {"event_id", "ticker", "event_time"}
    for name, df in [(args.left_name, left), (args.right_name, right)]:
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"{name} missing required columns: {missing}")

    compare_cols = [
        "llm_event_type",
        "llm_event_direction",
        "llm_event_scope",
        "llm_time_horizon",
        "llm_sentiment_score",
        "llm_materiality_score",
        "llm_novelty_score",
        "llm_catalyst_strength",
        "llm_confidence",
        "llm_explanation_short",
        "classifier_model",
    ]

    keep = ["event_id", "ticker", "event_time"] + [c for c in compare_cols if c in left.columns]
    left = left[keep].copy()
    left = left.rename(
        columns={
            c: f"{args.left_name}_{c}"
            for c in left.columns
            if c not in {"event_id", "ticker", "event_time"}
        }
    )

    keep = ["event_id", "ticker", "event_time"] + [c for c in compare_cols if c in right.columns]
    right = right[keep].copy()
    right = right.rename(
        columns={
            c: f"{args.right_name}_{c}"
            for c in right.columns
            if c not in {"event_id", "ticker", "event_time"}
        }
    )

    out = left.merge(right, on=["event_id", "ticker", "event_time"], how="outer")

    metrics = {}
    pairs = [
        "llm_event_type",
        "llm_event_direction",
        "llm_event_scope",
        "llm_time_horizon",
    ]

    for col in pairs:
        a = f"{args.left_name}_{col}"
        b = f"{args.right_name}_{col}"
        if a in out.columns and b in out.columns:
            valid = out[a].notna() & out[b].notna()
            metrics[f"{col}_agreement"] = float((out.loc[valid, a] == out.loc[valid, b]).mean()) if valid.any() else None

    numeric_pairs = [
        "llm_sentiment_score",
        "llm_materiality_score",
        "llm_novelty_score",
        "llm_catalyst_strength",
        "llm_confidence",
    ]

    for col in numeric_pairs:
        a = f"{args.left_name}_{col}"
        b = f"{args.right_name}_{col}"
        if a in out.columns and b in out.columns:
            diff = pd.to_numeric(out[a], errors="coerce") - pd.to_numeric(out[b], errors="coerce")
            metrics[f"{col}_mean_abs_diff"] = float(diff.abs().mean())

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print("== LLM classification comparison ==")
    print(f"left: {args.left_name} rows={len(left)}")
    print(f"right: {args.right_name} rows={len(right)}")
    print(f"joined rows: {len(out)}")
    print()

    for k, v in metrics.items():
        print(f"{k}: {v}")

    print()
    display_cols = [
        "ticker",
        "event_time",
        f"{args.left_name}_llm_event_type",
        f"{args.right_name}_llm_event_type",
        f"{args.left_name}_llm_event_direction",
        f"{args.right_name}_llm_event_direction",
        f"{args.left_name}_llm_materiality_score",
        f"{args.right_name}_llm_materiality_score",
        f"{args.left_name}_llm_confidence",
        f"{args.right_name}_llm_confidence",
    ]
    display_cols = [c for c in display_cols if c in out.columns]
    print(out[display_cols].to_string(index=False))

    print()
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
