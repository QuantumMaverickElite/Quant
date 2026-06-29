from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit provider/source balance in historical intelligence JSONL files.")
    parser.add_argument("--inputs", nargs="+", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--label", default="historical_sources")
    parser.add_argument("--max-provider-share", type=float, default=0.60)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        raise SystemExit(f"Missing input: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["_input_file"] = str(path)
                rows.append(row)
    return rows


def clean_provider(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"


def normalize_records(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "raw" in df.columns:
        raw_provider = []
        raw_domain = []
        for raw in df["raw"]:
            if isinstance(raw, dict):
                raw_provider.append(raw.get("provider") or raw.get("source") or raw.get("source_name"))
                raw_domain.append(raw.get("domain") or raw.get("source") or raw.get("publisher"))
            else:
                raw_provider.append(None)
                raw_domain.append(None)
        df["_raw_provider"] = raw_provider
        df["_raw_domain"] = raw_domain
    else:
        df["_raw_provider"] = None
        df["_raw_domain"] = None

    df["provider"] = [
        clean_provider(provider or raw_provider)
        for provider, raw_provider in zip(df.get("provider", pd.Series(index=df.index)), df["_raw_provider"])
    ]
    if "source_kind" not in df.columns:
        df["source_kind"] = "unknown"
    if "query" not in df.columns:
        df["query"] = ""
    if "domain" not in df.columns:
        df["domain"] = df["_raw_domain"]
    df["domain"] = df["domain"].fillna("").astype(str).str.strip().replace("", "unknown")
    df["published_at"] = df.get("published_at", pd.Series(index=df.index)).fillna("").astype(str)
    df["published_day"] = df["published_at"].str.slice(0, 10)
    numeric_month = df["published_at"].str.slice(0, 6).str.fullmatch(r"\d{6}", na=False)
    df["published_month"] = df["published_at"].str.slice(0, 7)
    df.loc[numeric_month, "published_month"] = (
        df.loc[numeric_month, "published_at"].str.slice(0, 4) + "-" + df.loc[numeric_month, "published_at"].str.slice(4, 6)
    )
    df["relevance_score"] = pd.to_numeric(df.get("relevance_score"), errors="coerce")
    df["model_sentiment_score"] = pd.to_numeric(df.get("model_sentiment_score"), errors="coerce")
    return df


def write_outputs(df: pd.DataFrame, out_dir: Path, label: str, max_provider_share: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if df.empty:
        raise SystemExit("No source rows found.")

    provider_summary = (
        df.groupby(["provider", "source_kind"], dropna=False)
        .agg(
            rows=("provider", "size"),
            unique_queries=("query", "nunique"),
            unique_domains=("domain", "nunique"),
            first_published=("published_day", "min"),
            last_published=("published_day", "max"),
            avg_relevance=("relevance_score", "mean"),
            sentiment_coverage=("model_sentiment_score", lambda s: float(s.notna().mean())),
        )
        .reset_index()
        .sort_values("rows", ascending=False)
    )
    provider_summary["row_share"] = provider_summary["rows"] / provider_summary["rows"].sum()
    provider_summary.to_csv(out_dir / f"{label}_provider_summary.csv", index=False)

    query_provider = pd.crosstab(df["query"], df["provider"])
    query_provider.to_csv(out_dir / f"{label}_query_provider_matrix.csv")

    month_provider = pd.crosstab(df["published_month"], df["provider"])
    month_provider.to_csv(out_dir / f"{label}_month_provider_matrix.csv")

    domain_summary = (
        df.groupby(["domain", "provider"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values("rows", ascending=False)
        .head(100)
    )
    domain_summary.to_csv(out_dir / f"{label}_top_domains.csv", index=False)

    top_share = float(provider_summary["row_share"].max()) if not provider_summary.empty else 0.0
    warnings: list[str] = []
    if top_share > max_provider_share:
        top_provider = str(provider_summary.iloc[0]["provider"])
        warnings.append(
            f"Provider concentration warning: {top_provider} is {top_share:.1%} of rows, "
            f"above threshold {max_provider_share:.1%}."
        )
    low_query_coverage = int((query_provider.gt(0).sum(axis=1) < 2).sum())
    if low_query_coverage:
        warnings.append(f"{low_query_coverage} queries have records from fewer than 2 providers.")

    summary = [
        f"rows: {len(df):,}",
        f"providers: {df['provider'].nunique():,}",
        f"queries: {df['query'].nunique():,}",
        f"domains: {df['domain'].nunique():,}",
        f"top_provider_share: {top_share:.4f}",
        "",
        "warnings:",
        *(warnings or ["none"]),
    ]
    (out_dir / f"{label}_source_mix_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("\n".join(summary))
    print(f"Saved provider summary: {out_dir / f'{label}_provider_summary.csv'}")
    print(f"Saved query/provider matrix: {out_dir / f'{label}_query_provider_matrix.csv'}")
    print(f"Saved month/provider matrix: {out_dir / f'{label}_month_provider_matrix.csv'}")


def main() -> None:
    args = parse_args()
    rows: list[dict] = []
    for path in args.inputs:
        rows.extend(read_jsonl(path))
    df = normalize_records(rows)
    write_outputs(df, args.out_dir, args.label, args.max_provider_share)


if __name__ == "__main__":
    main()
