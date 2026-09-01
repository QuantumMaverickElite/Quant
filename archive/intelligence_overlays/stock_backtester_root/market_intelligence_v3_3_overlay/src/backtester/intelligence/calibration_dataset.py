from __future__ import annotations

from pathlib import Path

import pandas as pd

from .candidates import detect_date_column, detect_ticker_column, read_table, write_table


def latest_per_query(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return features
    if "query" not in features.columns:
        raise ValueError("features must contain query column")
    out = features.copy()
    out["query"] = out["query"].astype(str).str.upper()
    if "as_of" in out.columns:
        out["_as_of"] = pd.to_datetime(out["as_of"], errors="coerce")
        out = out.sort_values("_as_of").drop(columns=["_as_of"])
    return out.drop_duplicates("query", keep="last")


def build_calibration_dataset(
    *,
    labeled_signals_path: str | Path,
    out_path: str | Path,
    intelligence_features_csv: str | Path | None = None,
    event_features_csv: str | Path | None = None,
    ticker_col: str | None = None,
    date_col: str | None = None,
) -> pd.DataFrame:
    df = read_table(labeled_signals_path).copy()
    ticker = detect_ticker_column(df, ticker_col)
    date = detect_date_column(df, date_col)
    if date is None:
        raise ValueError("Could not detect date column.")

    df["_calib_query"] = df[ticker].astype(str).str.upper()
    df["_calib_date"] = pd.to_datetime(df[date], errors="coerce")

    if intelligence_features_csv:
        intelligence = latest_per_query(pd.read_csv(intelligence_features_csv))
        rename = {
            col: f"intelligence_{col}"
            for col in intelligence.columns
            if col not in {"query", "as_of"}
        }
        intelligence = intelligence.rename(columns=rename)
        df = df.merge(intelligence, left_on="_calib_query", right_on="query", how="left")
        df = df.drop(columns=["query"], errors="ignore")

    if event_features_csv:
        events = latest_per_query(pd.read_csv(event_features_csv))
        rename = {col: f"event_{col}" for col in events.columns if col != "query"}
        events = events.rename(columns=rename)
        df = df.merge(events, left_on="_calib_query", right_on="query", how="left")
        df = df.drop(columns=["query"], errors="ignore")

    df = df.drop(columns=["_calib_query"])
    write_table(df, out_path)
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    prefixes = (
        "intelligence_",
        "event_",
        "sec_",
    )
    explicit = {
        "adjusted_confidence",
        "signal_score",
        "confidence",
        "price_action_risk",
        "regime_break_score",
        "sentiment_score",
        "contextual_event_risk",
    }
    cols: list[str] = []
    for col in df.columns:
        if col in explicit or col.startswith(prefixes):
            if pd.api.types.is_numeric_dtype(df[col]):
                cols.append(col)
    return sorted(set(cols))
