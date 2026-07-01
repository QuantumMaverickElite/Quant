from __future__ import annotations

from pathlib import Path
import math
import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table type: {path}")


def build_event_day_impact_dataset(
    *,
    event_impact_path: str | Path,
    horizon: int = 5,
    benchmark_ticker: str = "SPY",
) -> pd.DataFrame:
    df = read_table(event_impact_path).copy()

    base_col = f"event_base_date_{horizon}d"
    alpha_col = f"forward_alpha_vs_{benchmark_ticker.lower()}_{horizon}d"
    return_col = f"forward_return_{horizon}d"
    drawdown_col = f"forward_drawdown_{horizon}d"
    vol_col = f"forward_volatility_{horizon}d"

    required = {"ticker", "event_id", "provider", base_col, alpha_col}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"event impact table missing required columns: {missing}")

    df = df.loc[:, ~df.columns.duplicated()].copy()

    df["ticker"] = df["ticker"].astype(str).str.upper()
    df[base_col] = pd.to_datetime(df[base_col], errors="coerce").dt.normalize()
    df[alpha_col] = pd.to_numeric(df[alpha_col], errors="coerce")

    train = df[df[alpha_col].notna() & df[base_col].notna()].copy()

    event_type_cols = [
        c for c in train.columns
        if c.startswith("event_type_") and not c.endswith("_count")
    ]

    for col in event_type_cols:
        train[col] = pd.to_numeric(train[col], errors="coerce").fillna(0).astype(int)

    for col in ["lexical_sentiment_raw", "positive_term_count", "negative_term_count"]:
        if col not in train.columns:
            train[col] = 0
        train[col] = pd.to_numeric(train[col], errors="coerce").fillna(0)

    if "event_after_market_close" not in train.columns:
        train["event_after_market_close"] = 0
    train["event_after_market_close"] = pd.to_numeric(
        train["event_after_market_close"], errors="coerce"
    ).fillna(0).astype(int)

    train["provider"] = train["provider"].astype(str)
    provider_dummies = pd.get_dummies(train["provider"], prefix="provider_src", dtype=int)
    train = pd.concat([train, provider_dummies], axis=1)
    provider_cols = list(provider_dummies.columns)

    group_cols = ["ticker", base_col]

    named_aggs = {
        "event_count": ("event_id", "count"),
        "provider_count": ("provider", "nunique"),
        "sentiment_mean": ("lexical_sentiment_raw", "mean"),
        "sentiment_max": ("lexical_sentiment_raw", "max"),
        "sentiment_min": ("lexical_sentiment_raw", "min"),
        "sentiment_sum": ("lexical_sentiment_raw", "sum"),
        "positive_term_count_sum": ("positive_term_count", "sum"),
        "positive_term_count_max": ("positive_term_count", "max"),
        "negative_term_count_sum": ("negative_term_count", "sum"),
        "negative_term_count_max": ("negative_term_count", "max"),
        "after_close_event_count": ("event_after_market_close", "sum"),
        "target_forward_alpha": (alpha_col, "first"),
    }

    if "article_id" in train.columns:
        named_aggs["unique_article_count"] = ("article_id", "nunique")
    else:
        named_aggs["unique_article_count"] = ("event_id", "nunique")

    if "title" in train.columns:
        named_aggs["unique_title_count"] = ("title", "nunique")
    else:
        named_aggs["unique_title_count"] = ("event_id", "nunique")

    if return_col in train.columns:
        named_aggs["target_forward_return"] = (return_col, "first")
    if drawdown_col in train.columns:
        named_aggs["target_forward_drawdown"] = (drawdown_col, "first")
    if vol_col in train.columns:
        named_aggs["target_forward_volatility"] = (vol_col, "first")

    for col in event_type_cols:
        named_aggs[f"{col}_count"] = (col, "sum")

    for col in provider_cols:
        named_aggs[f"{col}_count"] = (col, "sum")

    out = train.groupby(group_cols, as_index=False).agg(**named_aggs)
    out = out.rename(columns={base_col: "event_base_date"})

    out["target_positive_alpha"] = (out["target_forward_alpha"] > 0).astype(int)
    out["target_horizon_days"] = horizon
    out["event_density_log"] = out["event_count"].astype(float).add(1.0).map(math.log)
    out["multi_provider_flag"] = (out["provider_count"] >= 2).astype(int)

    out = out.sort_values(["event_base_date", "ticker"]).reset_index(drop=True)
    return out


def write_event_day_impact_dataset(df: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".parquet":
        df.to_parquet(out_path, index=False)
        df.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".csv":
        df.to_csv(out_path, index=False)
        df.to_parquet(out_path.with_suffix(".parquet"), index=False)
    else:
        raise ValueError(f"Unsupported output type: {out_path}")
