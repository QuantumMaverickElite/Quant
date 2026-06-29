from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .candidates import detect_date_column, detect_ticker_column, read_table, write_table


DEFAULT_WINDOWS = (1, 7, 30)
IMPORTANT_FORMS = ("8-K", "10-Q", "10-K", "S-1", "424B", "DEF 14A")


def read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def sec_records_to_frame(path: str | Path) -> pd.DataFrame:
    rows = read_jsonl(path)
    if not rows:
        return pd.DataFrame(
            columns=[
                "query",
                "published_at",
                "provider",
                "source_kind",
                "form",
                "filing_date",
                "report_date",
            ]
        )
    out = pd.DataFrame(rows)
    out["query"] = out["query"].astype(str).str.upper()
    out["published_at_dt"] = pd.to_datetime(out["published_at"], errors="coerce")
    raw = out["raw"].apply(lambda x: x if isinstance(x, dict) else {})
    out["form"] = raw.apply(lambda x: str(x.get("form") or "").upper())
    out["filing_date"] = raw.apply(lambda x: x.get("filingDate"))
    out["report_date"] = raw.apply(lambda x: x.get("reportDate"))
    out["accession_number"] = raw.apply(lambda x: x.get("accessionNumber"))
    out = out.dropna(subset=["published_at_dt", "query"])
    return out


def filing_pressure(form: str) -> float:
    form = str(form or "").upper()
    if form == "8-K":
        return 0.35
    if form == "10-Q":
        return 0.25
    if form == "10-K":
        return 0.30
    if form.startswith("S-1"):
        return 0.45
    if form.startswith("424B"):
        return 0.40
    if form.startswith("DEF"):
        return 0.15
    return 0.10


def empty_feature_row(query: str, signal_date: pd.Timestamp) -> dict:
    return {
        "query": query,
        "date": signal_date,
        "sec_days_since_latest_filing": np.nan,
        "sec_latest_form": "",
        "sec_latest_filing_date": pd.NaT,
        "sec_filing_pressure_30d": 0.0,
    }


def build_sec_point_in_time_features(
    *,
    sec_sources_jsonl: str | Path,
    signal_dates: pd.DataFrame,
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
    ticker_col: str = "ticker",
    date_col: str = "date",
) -> pd.DataFrame:
    filings = sec_records_to_frame(sec_sources_jsonl)
    signals = signal_dates[[ticker_col, date_col]].drop_duplicates().copy()
    signals[ticker_col] = signals[ticker_col].astype(str).str.upper()
    signals[date_col] = pd.to_datetime(signals[date_col], errors="coerce")
    signals = signals.dropna(subset=[ticker_col, date_col]).sort_values([ticker_col, date_col])

    rows: list[dict] = []
    for _, signal in signals.iterrows():
        query = str(signal[ticker_col]).upper()
        signal_date = pd.Timestamp(signal[date_col])
        sub = filings[filings["query"].eq(query)].copy()
        past = sub[sub["published_at_dt"].le(signal_date)].copy()

        row = empty_feature_row(query, signal_date)
        if len(past):
            latest = past.sort_values("published_at_dt").iloc[-1]
            days_since = (signal_date.normalize() - latest["published_at_dt"].normalize()).days
            row["sec_days_since_latest_filing"] = float(max(0, days_since))
            row["sec_latest_form"] = latest["form"]
            row["sec_latest_filing_date"] = latest["published_at_dt"]

        for window in windows:
            start = signal_date - pd.Timedelta(days=window)
            win = past[past["published_at_dt"].gt(start)]
            row[f"sec_filing_count_{window}d"] = float(len(win))
            row[f"sec_filing_pressure_{window}d"] = float(sum(filing_pressure(form) for form in win["form"]))
            for form in IMPORTANT_FORMS:
                safe_form = form.lower().replace("-", "").replace(" ", "_")
                form_win = win[win["form"].eq(form)]
                row[f"sec_{safe_form}_count_{window}d"] = float(len(form_win))
                row[f"sec_has_{safe_form}_{window}d"] = float(len(form_win) > 0)

        rows.append(row)

    return pd.DataFrame(rows)


def signal_dates_from_table(signals_path: str | Path, ticker_col: str | None = None, date_col: str | None = None) -> tuple[pd.DataFrame, str, str]:
    signals = read_table(signals_path)
    ticker = detect_ticker_column(signals, ticker_col)
    date = detect_date_column(signals, date_col)
    if date is None:
        raise ValueError("Could not detect signal date column.")
    return signals, ticker, date


def build_and_save_sec_features(
    *,
    sec_sources_jsonl: str | Path,
    signals_path: str | Path,
    out_path: str | Path,
    ticker_col: str | None = None,
    date_col: str | None = None,
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    signals, ticker, date = signal_dates_from_table(signals_path, ticker_col=ticker_col, date_col=date_col)
    features = build_sec_point_in_time_features(
        sec_sources_jsonl=sec_sources_jsonl,
        signal_dates=signals,
        windows=windows,
        ticker_col=ticker,
        date_col=date,
    )
    write_table(features, out_path)
    return features


def join_sec_features_to_signals(
    *,
    signals_path: str | Path,
    sec_features_path: str | Path,
    out_path: str | Path,
    ticker_col: str | None = None,
    date_col: str | None = None,
) -> pd.DataFrame:
    signals = read_table(signals_path)
    ticker = detect_ticker_column(signals, ticker_col)
    date = detect_date_column(signals, date_col)
    if date is None:
        raise ValueError("Could not detect signal date column.")
    features = read_table(sec_features_path)
    left = signals.copy()
    left["_sec_query"] = left[ticker].astype(str).str.upper()
    left["_sec_date"] = pd.to_datetime(left[date], errors="coerce")
    right = features.copy()
    right["_sec_query"] = right["query"].astype(str).str.upper()
    right["_sec_date"] = pd.to_datetime(right["date"], errors="coerce")
    out = left.merge(right.drop(columns=["query", "date"], errors="ignore"), on=["_sec_query", "_sec_date"], how="left")
    out = out.drop(columns=["_sec_query", "_sec_date"])
    write_table(out, out_path)
    return out
