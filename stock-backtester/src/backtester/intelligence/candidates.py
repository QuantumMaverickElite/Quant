from __future__ import annotations

from pathlib import Path

import pandas as pd


TICKER_COLUMNS = [
    "ticker",
    "symbol",
    "query",
    "asset",
    "stock",
    "candidate",
    "candidate_ticker",
]

DATE_COLUMNS = [
    "date",
    "signal_date",
    "as_of",
    "timestamp",
    "datetime",
]

RANK_COLUMNS_DESC = [
    "adjusted_confidence",
    "confidence",
    "signal_score",
    "score",
    "expected_return",
    "mean_reversion_score",
    "rank_score",
]

RANK_COLUMNS_ASC = [
    "rank",
    "market_cap_rank",
]


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table type: {path}")


def write_table(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
    elif suffix == ".csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError(f"Unsupported table type: {path}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def detect_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {str(col).lower(): str(col) for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def detect_ticker_column(df: pd.DataFrame, ticker_col: str | None = None) -> str:
    if ticker_col:
        if ticker_col not in df.columns:
            raise ValueError(f"Ticker column not found: {ticker_col}")
        return ticker_col
    detected = detect_column(df, TICKER_COLUMNS)
    if not detected:
        raise ValueError(f"Could not detect ticker column. Tried: {', '.join(TICKER_COLUMNS)}")
    return detected


def detect_date_column(df: pd.DataFrame, date_col: str | None = None) -> str | None:
    if date_col:
        if date_col not in df.columns:
            raise ValueError(f"Date column not found: {date_col}")
        return date_col
    return detect_column(df, DATE_COLUMNS)


def detect_rank_column(df: pd.DataFrame, rank_col: str | None = None) -> tuple[str | None, bool]:
    if rank_col:
        if rank_col not in df.columns:
            raise ValueError(f"Rank column not found: {rank_col}")
        return rank_col, rank_col.lower() in RANK_COLUMNS_ASC

    desc_col = detect_column(df, RANK_COLUMNS_DESC)
    if desc_col:
        return desc_col, False
    asc_col = detect_column(df, RANK_COLUMNS_ASC)
    if asc_col:
        return asc_col, True
    return None, False


def clean_ticker(value: object) -> str:
    return str(value).strip().upper()


def filter_latest_date(df: pd.DataFrame, date_col: str | None = None) -> pd.DataFrame:
    detected = detect_date_column(df, date_col)
    if not detected:
        raise ValueError("Could not detect date column for latest-date filtering.")
    out = df.copy()
    out["_intelligence_date"] = pd.to_datetime(out[detected], errors="coerce")
    latest = out["_intelligence_date"].max()
    if pd.isna(latest):
        raise ValueError(f"Could not parse any usable dates from column: {detected}")
    out = out[out["_intelligence_date"].eq(latest)].drop(columns=["_intelligence_date"])
    return out


def load_candidate_queries(
    path: str | Path,
    *,
    top_n: int = 50,
    ticker_col: str | None = None,
    rank_col: str | None = None,
    rank_ascending: bool | None = None,
    date_col: str | None = None,
    latest_date_only: bool = False,
) -> list[str]:
    df = normalize_columns(read_table(path))
    if latest_date_only:
        df = filter_latest_date(df, date_col)
    detected_ticker_col = detect_ticker_column(df, ticker_col)
    detected_rank_col, detected_rank_ascending = detect_rank_column(df, rank_col)
    if rank_ascending is None:
        rank_ascending = detected_rank_ascending

    df = df.copy()
    df["_intelligence_query"] = df[detected_ticker_col].map(clean_ticker)
    df = df[df["_intelligence_query"].ne("") & df["_intelligence_query"].ne("NAN")]

    if detected_rank_col:
        df = df.sort_values(detected_rank_col, ascending=rank_ascending, na_position="last")

    queries = df["_intelligence_query"].drop_duplicates().head(top_n).tolist()
    return queries


def action_label(regime_break_score: float) -> str:
    if regime_break_score < 0.30:
        return "same_regime_scale_in_allowed"
    if regime_break_score < 0.55:
        return "caution_hold_no_adding"
    if regime_break_score < 0.75:
        return "likely_regime_damage_do_not_average_down"
    return "thesis_break_risk_reduce_or_wait"
