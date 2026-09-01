from __future__ import annotations

from pathlib import Path

import pandas as pd

from .candidates import detect_date_column, detect_ticker_column, read_table, write_table


DEFAULT_RANK_COLUMNS = (
    "allocator_confidence_pre_intelligence",
    "allocator_confidence_intelligence_adjusted",
    "adjusted_confidence",
    "confidence",
    "signal_score",
    "mean_reversion_score",
    "score",
)


def read_ticker_file(path: str | Path | None) -> set[str] | None:
    if not path:
        return None
    tickers: set[str] = set()
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            value = line.strip().upper()
            if value:
                tickers.add(value)
    return tickers


def detect_rank_column(df: pd.DataFrame, rank_col: str | None = None) -> str:
    if rank_col:
        if rank_col not in df.columns:
            raise ValueError(f"Rank column not found: {rank_col}")
        return rank_col
    lower_map = {str(col).lower(): str(col) for col in df.columns}
    for candidate in DEFAULT_RANK_COLUMNS:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    raise ValueError(f"Could not detect rank column. Tried: {', '.join(DEFAULT_RANK_COLUMNS)}")


def build_historical_panel_seed(
    *,
    signals_path: str | Path,
    out_path: str | Path,
    ticker_col: str | None = None,
    date_col: str | None = None,
    rank_col: str | None = None,
    tickers_file: str | Path | None = None,
    start: str | None = None,
    end: str | None = None,
    top_n_per_date: int = 50,
    min_rank_value: float | None = None,
    max_dates: int | None = None,
    exclude_latest_date: bool = False,
) -> pd.DataFrame:
    df = read_table(signals_path).copy()
    ticker = detect_ticker_column(df, ticker_col)
    date = detect_date_column(df, date_col)
    if date is None:
        raise ValueError("Could not detect date column.")
    rank = detect_rank_column(df, rank_col)

    out = df.copy()
    out["_hist_query"] = out[ticker].astype(str).str.upper().str.strip()
    out["_hist_date"] = pd.to_datetime(out[date], errors="coerce")
    out["_hist_rank"] = pd.to_numeric(out[rank], errors="coerce")
    out = out[out["_hist_query"].ne("") & out["_hist_query"].ne("NAN")]
    out = out.dropna(subset=["_hist_date", "_hist_rank"])

    allowed = read_ticker_file(tickers_file)
    if allowed is not None:
        out = out[out["_hist_query"].isin(allowed)]
    if start:
        out = out[out["_hist_date"].ge(pd.Timestamp(start))]
    if end:
        out = out[out["_hist_date"].le(pd.Timestamp(end))]
    if exclude_latest_date and not out.empty:
        latest = out["_hist_date"].max()
        out = out[out["_hist_date"].lt(latest)]
    if min_rank_value is not None:
        out = out[out["_hist_rank"].ge(min_rank_value)]

    out = out.sort_values(["_hist_date", "_hist_rank"], ascending=[True, False])
    out = out.drop_duplicates(["_hist_date", "_hist_query"], keep="first")

    if max_dates is not None:
        dates = sorted(out["_hist_date"].dropna().unique())[-int(max_dates) :]
        out = out[out["_hist_date"].isin(dates)]

    if top_n_per_date > 0:
        out = out.groupby("_hist_date", group_keys=False).head(top_n_per_date)

    out = out.drop(columns=["_hist_query", "_hist_date", "_hist_rank"], errors="ignore")
    write_table(out, out_path)
    return out
