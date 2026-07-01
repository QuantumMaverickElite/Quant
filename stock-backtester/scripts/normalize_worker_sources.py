from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Normalize worker source JSONL into a parquet table.")
    ap.add_argument("--input", required=True, help="Worker source JSONL input.")
    ap.add_argument("--out", required=True, help="Normalized parquet output.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    src = Path(args.input)
    out = Path(args.out)

    df = pd.read_json(src, lines=True)

    if "ticker" not in df.columns:
        if "query" not in df.columns:
            raise SystemExit("input must contain either ticker or query")
        df["ticker"] = df["query"]

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    nested_types = (dict, list, tuple, set)

    def has_nested(series: pd.Series) -> bool:
        return bool(series.map(lambda x: isinstance(x, nested_types)).any())

    def clean_cell(x):
        if isinstance(x, nested_types):
            return json.dumps(x, sort_keys=True, default=str)
        return x

    for col in df.columns:
        if has_nested(df[col]):
            df[col] = df[col].map(clean_cell)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    print(f"wrote: {out}")
    print(f"rows: {len(df)}")
    print(f"columns: {len(df.columns)}")


if __name__ == "__main__":
    main()
