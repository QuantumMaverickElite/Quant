from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .candidates import detect_date_column, detect_ticker_column, read_table, write_table


DEFAULT_WINDOWS = (1, 7, 30, 90)


def read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def parse_source_datetime(value: object) -> pd.Timestamp:
    if value is None or value == "":
        return pd.NaT
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return pd.to_datetime(text, format="%Y%m%d", errors="coerce", utc=True)
    if len(text) == 13 and text[:8].isdigit() and text[8] == "T":
        return pd.to_datetime(text, format="%Y%m%dT%H%M", errors="coerce", utc=True)
    return pd.to_datetime(text, errors="coerce", utc=True)


def alpha_vantage_sentiment(raw: dict) -> float:
    try:
        return float(raw.get("overall_sentiment_score"))
    except (TypeError, ValueError):
        return np.nan


def recommendation_pressure(raw: dict) -> float:
    strong_buy = float(raw.get("strongBuy") or 0)
    buy = float(raw.get("buy") or 0)
    hold = float(raw.get("hold") or 0)
    sell = float(raw.get("sell") or 0)
    strong_sell = float(raw.get("strongSell") or 0)
    total = strong_buy + buy + hold + sell + strong_sell
    if total <= 0:
        return np.nan
    return (2.0 * strong_buy + buy - sell - 2.0 * strong_sell) / (2.0 * total)


def provider_insight_sentiment(raw: dict, query: str) -> float:
    mapping = {
        "positive": 1.0,
        "bullish": 1.0,
        "negative": -1.0,
        "bearish": -1.0,
        "neutral": 0.0,
    }
    insights = raw.get("insights")
    if not isinstance(insights, list):
        return np.nan
    query = str(query or "").upper()
    values: list[float] = []
    for item in insights:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        if query and ticker and ticker != query:
            continue
        sentiment = str(item.get("sentiment") or "").strip().lower()
        if sentiment in mapping:
            values.append(mapping[sentiment])
    if not values:
        return np.nan
    return float(np.mean(values))


def source_sentiment(row: pd.Series) -> float:
    provider = str(row.get("provider") or "")
    raw = row.get("raw")
    raw = raw if isinstance(raw, dict) else {}
    try:
        return float(raw["model_sentiment_score"])
    except (KeyError, TypeError, ValueError):
        pass
    if provider == "alpha_vantage_news_sentiment":
        return alpha_vantage_sentiment(raw)
    if provider == "finnhub_recommendation_trends":
        return recommendation_pressure(raw)
    if provider in {"polygon_ticker_news", "massive_ticker_news"}:
        return provider_insight_sentiment(raw, str(row.get("query") or ""))
    return np.nan


def source_records_to_frame(path: str | Path) -> pd.DataFrame:
    rows = read_jsonl(path)
    if not rows:
        return pd.DataFrame(columns=["query", "published_at_dt", "source_kind", "provider", "sentiment_score"])
    df = pd.DataFrame(rows)
    df["query"] = df["query"].astype(str).str.upper()
    df["published_at_dt"] = df["published_at"].map(parse_source_datetime)
    if "source_kind" not in df.columns:
        df["source_kind"] = ""
    if "provider" not in df.columns:
        df["provider"] = ""
    if "relevance_score" not in df.columns:
        df["relevance_score"] = 1.0
    df["source_kind"] = df["source_kind"].astype(str)
    df["provider"] = df["provider"].astype(str)
    df["relevance_score"] = pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0.0)
    if "raw" not in df.columns:
        df["raw"] = [{} for _ in range(len(df))]
    df["sentiment_score"] = df.apply(source_sentiment, axis=1)
    df = df.dropna(subset=["published_at_dt", "query"])
    return df


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    vals = pd.to_numeric(values, errors="coerce")
    wts = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    mask = vals.notna() & wts.gt(0)
    if not mask.any():
        return np.nan
    return float(np.average(vals[mask], weights=wts[mask]))


def empty_feature_row(query: str, signal_date: pd.Timestamp) -> dict:
    return {
        "query": query,
        "date": signal_date,
        "news_days_since_latest": np.nan,
        "news_latest_provider": "",
        "news_latest_source_kind": "",
        "news_latest_sentiment": np.nan,
    }


def build_news_point_in_time_features(
    *,
    sources_jsonl: str | Path,
    signal_dates: pd.DataFrame,
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
    ticker_col: str = "ticker",
    date_col: str = "date",
) -> pd.DataFrame:
    sources = source_records_to_frame(sources_jsonl)
    signals = signal_dates[[ticker_col, date_col]].drop_duplicates().copy()
    signals[ticker_col] = signals[ticker_col].astype(str).str.upper()
    signals[date_col] = pd.to_datetime(signals[date_col], errors="coerce")
    signals = signals.dropna(subset=[ticker_col, date_col]).sort_values([ticker_col, date_col])

    rows: list[dict] = []
    for _, signal in signals.iterrows():
        query = str(signal[ticker_col]).upper()
        signal_date = pd.Timestamp(signal[date_col])
        sub = sources[sources["query"].eq(query)].copy()
        past = sub[sub["published_at_dt"].dt.tz_localize(None).le(signal_date)].copy()

        row = empty_feature_row(query, signal_date)
        if len(past):
            latest = past.sort_values("published_at_dt").iloc[-1]
            latest_date = latest["published_at_dt"].tz_localize(None)
            row["news_days_since_latest"] = float(max(0, (signal_date.normalize() - latest_date.normalize()).days))
            row["news_latest_provider"] = latest["provider"]
            row["news_latest_source_kind"] = latest["source_kind"]
            row["news_latest_sentiment"] = latest["sentiment_score"]

        for window in windows:
            start = signal_date - pd.Timedelta(days=window)
            win = past[past["published_at_dt"].dt.tz_localize(None).gt(start)]
            news = win[~win["source_kind"].eq("analyst_recommendation")]
            analyst = win[win["source_kind"].eq("analyst_recommendation")]

            row[f"news_count_{window}d"] = float(len(news))
            row[f"news_relevance_sum_{window}d"] = float(news["relevance_score"].sum()) if len(news) else 0.0
            row[f"news_relevance_mean_{window}d"] = float(news["relevance_score"].mean()) if len(news) else np.nan
            row[f"news_sentiment_mean_{window}d"] = float(news["sentiment_score"].mean()) if news["sentiment_score"].notna().any() else np.nan
            row[f"news_sentiment_weighted_{window}d"] = weighted_mean(news["sentiment_score"], news["relevance_score"])
            row[f"news_positive_count_{window}d"] = float((news["sentiment_score"] > 0.05).sum())
            row[f"news_negative_count_{window}d"] = float((news["sentiment_score"] < -0.05).sum())

            row[f"analyst_recommendation_count_{window}d"] = float(len(analyst))
            row[f"analyst_pressure_mean_{window}d"] = (
                float(analyst["sentiment_score"].mean()) if analyst["sentiment_score"].notna().any() else np.nan
            )
            row[f"analyst_pressure_latest_{window}d"] = (
                float(analyst.sort_values("published_at_dt")["sentiment_score"].dropna().iloc[-1])
                if analyst["sentiment_score"].notna().any()
                else np.nan
            )

        rows.append(row)

    return pd.DataFrame(rows)


def build_and_save_news_features(
    *,
    sources_jsonl: str | Path,
    signals_path: str | Path,
    out_path: str | Path,
    ticker_col: str | None = None,
    date_col: str | None = None,
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    signals = read_table(signals_path)
    ticker = detect_ticker_column(signals, ticker_col)
    date = detect_date_column(signals, date_col)
    if date is None:
        raise ValueError("Could not detect signal date column.")
    features = build_news_point_in_time_features(
        sources_jsonl=sources_jsonl,
        signal_dates=signals,
        windows=windows,
        ticker_col=ticker,
        date_col=date,
    )
    write_table(features, out_path)
    return features


def join_news_features_to_signals(
    *,
    signals_path: str | Path,
    news_features_path: str | Path,
    out_path: str | Path,
    ticker_col: str | None = None,
    date_col: str | None = None,
) -> pd.DataFrame:
    signals = read_table(signals_path)
    ticker = detect_ticker_column(signals, ticker_col)
    date = detect_date_column(signals, date_col)
    if date is None:
        raise ValueError("Could not detect signal date column.")
    features = read_table(news_features_path)
    left = signals.copy()
    left["_news_query"] = left[ticker].astype(str).str.upper()
    left["_news_date"] = pd.to_datetime(left[date], errors="coerce")
    right = features.copy()
    right["_news_query"] = right["query"].astype(str).str.upper()
    right["_news_date"] = pd.to_datetime(right["date"], errors="coerce")
    out = left.merge(right.drop(columns=["query", "date"], errors="ignore"), on=["_news_query", "_news_date"], how="left")
    out = out.drop(columns=["_news_query", "_news_date"])
    write_table(out, out_path)
    return out
