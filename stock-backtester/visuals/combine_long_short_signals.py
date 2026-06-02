from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Combine long and short peer-spread signal parquet files."
    )
    p.add_argument("--long-signals", required=True)
    p.add_argument("--short-signals", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--dedupe",
        action="store_true",
        help="Keep strongest duplicate date/direction/ticker rows.",
    )
    return p.parse_args()


def require_columns(df: pd.DataFrame, path: Path) -> None:
    required = {"date", "ticker", "adjusted_confidence"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def main() -> None:
    args = parse_args()

    long_path = Path(args.long_signals)
    short_path = Path(args.short_signals)
    out_path = Path(args.out)

    long_df = pd.read_parquet(long_path).copy()
    short_df = pd.read_parquet(short_path).copy()

    require_columns(long_df, long_path)
    require_columns(short_df, short_path)

    long_df["date"] = pd.to_datetime(long_df["date"])
    short_df["date"] = pd.to_datetime(short_df["date"])

    long_df["direction"] = "long"
    short_df["direction"] = "short"

    combined = pd.concat([long_df, short_df], ignore_index=True)

    if args.dedupe:
        combined = (
            combined.sort_values(
                ["date", "direction", "ticker", "adjusted_confidence"],
                ascending=[True, True, True, False],
            )
            .drop_duplicates(["date", "direction", "ticker"], keep="first")
            .reset_index(drop=True)
        )

    combined = combined.sort_values(
        ["date", "direction", "adjusted_confidence"],
        ascending=[True, True, False],
    ).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)

    print("Saved:", out_path)
    print("Rows:", len(combined))
    print("Dates:", combined["date"].nunique())
    print("Tickers:", combined["ticker"].nunique())
    print("Date range:", combined["date"].min().date(), "→", combined["date"].max().date())
    print()
    print(combined["direction"].value_counts().to_string())


if __name__ == "__main__":
    main()
