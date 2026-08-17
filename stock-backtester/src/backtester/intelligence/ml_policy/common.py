"""Shared column-selection helpers for the ML-policy research family."""

from __future__ import annotations

import pandas as pd


def detect_col(df: pd.DataFrame, requested: str | None, candidates: tuple[str, ...], label: str) -> str:
    if requested:
        if requested not in df.columns:
            raise ValueError(f"{label} column not found: {requested}")
        return requested
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Could not detect {label} column. Tried: {', '.join(candidates)}")


def detect_ticker_col(df: pd.DataFrame, requested: str | None) -> str:
    return detect_col(df, requested, ("ticker", "query", "symbol"), "ticker")


def detect_date_col(df: pd.DataFrame, requested: str | None) -> str:
    return detect_col(df, requested, ("date", "signal_date", "as_of", "timestamp"), "date")

