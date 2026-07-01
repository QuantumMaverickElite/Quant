#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


KEYWORD_BUCKETS: list[tuple[str, list[str]]] = [
    (
        "regulatory_clinical",
        [
            "fda",
            "phase 1",
            "phase 2",
            "phase 3",
            "clinical",
            "trial",
            "breakthrough therapy",
            "fast track",
            "pdufa",
            "approval",
            "drug",
            "therapy",
        ],
    ),
    (
        "earnings_guidance",
        [
            "earnings",
            "revenue",
            "eps",
            "guidance",
            "forecast",
            "quarter",
            "q1",
            "q2",
            "q3",
            "q4",
            "results",
        ],
    ),
    (
        "analyst_rating",
        [
            "upgrade",
            "downgrade",
            "price target",
            "initiated",
            "rating",
            "analyst",
            "outperform",
            "underperform",
        ],
    ),
    (
        "legal_regulatory",
        [
            "lawsuit",
            "sec",
            "investigation",
            "probe",
            "settlement",
            "antitrust",
            "fine",
            "fraud",
            "regulator",
        ],
    ),
    (
        "ma_deal",
        [
            "acquire",
            "acquisition",
            "merger",
            "takeover",
            "deal",
            "buyout",
            "strategic review",
            "sale",
        ],
    ),
    (
        "capital_structure",
        [
            "offering",
            "debt",
            "notes",
            "dividend",
            "buyback",
            "repurchase",
            "split",
            "warrant",
            "at-the-market",
        ],
    ),
    (
        "product_customer",
        [
            "launch",
            "contract",
            "partnership",
            "customer",
            "order",
            "supply",
            "agreement",
            "collaboration",
        ],
    ),
    (
        "macro_market",
        [
            "fed",
            "rates",
            "inflation",
            "cpi",
            "jobs",
            "tariff",
            "china",
            "oil",
            "market",
            "nasdaq",
            "s&p",
            "treasury",
        ],
    ),
]


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)

    raise ValueError(f"Unsupported input type: {path}")


def stable_hash(value: object) -> int:
    text = "" if pd.isna(value) else str(value)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).lower()


def combined_text(row: pd.Series) -> str:
    parts = []
    for col in ["title", "summary", "description", "body", "text", "url"]:
        if col in row.index:
            parts.append(clean_text(row.get(col)))
    return " ".join(parts)


def keyword_bucket(row: pd.Series) -> str:
    text = combined_text(row)
    for bucket, keywords in KEYWORD_BUCKETS:
        if any(k in text for k in keywords):
            return bucket
    return "other"


def normalize_event_time(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "event_time" in out.columns:
        out["event_time"] = pd.to_datetime(out["event_time"], errors="coerce", utc=True)
    elif "published_at" in out.columns:
        out["event_time"] = pd.to_datetime(out["published_at"], errors="coerce", utc=True)
    elif "date" in out.columns:
        out["event_time"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    else:
        out["event_time"] = pd.NaT

    out["event_date"] = out["event_time"].dt.date.astype("string")
    return out


def pick_mixed_sample(
    df: pd.DataFrame,
    *,
    n: int,
    max_per_ticker: int,
    max_per_bucket: int,
    max_per_provider: int,
) -> pd.DataFrame:
    work = normalize_event_time(df)

    if "event_id" not in work.columns:
        raise ValueError("Input must contain event_id")

    if "ticker" not in work.columns:
        work["ticker"] = "UNKNOWN"

    if "provider" not in work.columns:
        work["provider"] = "UNKNOWN"

    work["sample_bucket"] = work.apply(keyword_bucket, axis=1)
    work["sample_hash"] = work["event_id"].map(stable_hash)

    # Prefer rows with usable title/text, then diversify deterministically.
    text_cols = [c for c in ["title", "summary", "description", "body", "text"] if c in work.columns]
    if text_cols:
        work["sample_text_len"] = work[text_cols].fillna("").astype(str).agg(" ".join, axis=1).str.len()
    else:
        work["sample_text_len"] = 0

    work = work.sort_values(
        ["sample_bucket", "ticker", "provider", "event_date", "sample_hash"],
        kind="mergesort",
    )

    chosen_rows = []
    ticker_counts: dict[str, int] = {}
    bucket_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    used: set[str] = set()

    # Round-robin by bucket first so one ticker/news family does not dominate.
    buckets = sorted(work["sample_bucket"].dropna().unique().tolist())

    while len(chosen_rows) < n:
        progressed = False

        for bucket in buckets:
            if len(chosen_rows) >= n:
                break

            chunk = work[work["sample_bucket"] == bucket]

            for _, row in chunk.iterrows():
                event_id = str(row["event_id"])
                ticker = str(row.get("ticker", "UNKNOWN"))
                provider = str(row.get("provider", "UNKNOWN"))
                bucket_name = str(row.get("sample_bucket", "other"))

                if event_id in used:
                    continue
                if ticker_counts.get(ticker, 0) >= max_per_ticker:
                    continue
                if bucket_counts.get(bucket_name, 0) >= max_per_bucket:
                    continue
                if provider_counts.get(provider, 0) >= max_per_provider:
                    continue

                chosen_rows.append(row)
                used.add(event_id)
                ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
                bucket_counts[bucket_name] = bucket_counts.get(bucket_name, 0) + 1
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
                progressed = True
                break

        if not progressed:
            break

    # If constraints are too tight, fill remaining rows while still avoiding duplicates.
    if len(chosen_rows) < n:
        for _, row in work.iterrows():
            if len(chosen_rows) >= n:
                break
            event_id = str(row["event_id"])
            if event_id in used:
                continue
            chosen_rows.append(row)
            used.add(event_id)

    out = pd.DataFrame(chosen_rows).reset_index(drop=True)

    helper_cols = ["sample_hash"]
    out = out.drop(columns=[c for c in helper_cols if c in out.columns])

    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--events",
        default="outputs/intelligence/event_fact_table.parquet",
        help="Input event fact table.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/llm_benchmark_mixed_50.parquet",
        help="Output benchmark sample path.",
    )
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--max-per-ticker", type=int, default=5)
    p.add_argument("--max-per-bucket", type=int, default=10)
    p.add_argument("--max-per-provider", type=int, default=25)
    args = p.parse_args()

    df = read_table(args.events)
    sample = pick_mixed_sample(
        df,
        n=args.n,
        max_per_ticker=args.max_per_ticker,
        max_per_bucket=args.max_per_bucket,
        max_per_provider=args.max_per_provider,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".parquet":
        sample.to_parquet(out_path, index=False)
        sample.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".csv":
        sample.to_csv(out_path, index=False)
        sample.to_parquet(out_path.with_suffix(".parquet"), index=False)
    else:
        raise ValueError("Output must be .parquet or .csv")

    print("== LLM benchmark mixed sample ==")
    print(f"input rows: {len(df)}")
    print(f"sample rows: {len(sample)}")
    print(f"wrote: {out_path}")

    print()
    print("tickers:")
    print(sample["ticker"].value_counts().head(30).to_string())

    print()
    print("providers:")
    print(sample["provider"].value_counts().to_string())

    print()
    print("sample buckets:")
    print(sample["sample_bucket"].value_counts().to_string())

    display_cols = [
        "event_id",
        "ticker",
        "event_time",
        "provider",
        "sample_bucket",
        "title",
    ]
    display_cols = [c for c in display_cols if c in sample.columns]

    print()
    print(sample[display_cols].head(25).to_string(index=False))


if __name__ == "__main__":
    main()
