from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .candidates import detect_date_column, detect_ticker_column, read_table, write_table
from .price_risk import download_prices, to_long_ohlcv


@dataclass(slots=True)
class OutcomeConfig:
    horizons: tuple[int, ...] = (5, 20)
    success_horizon: int = 20
    success_return_threshold: float = 0.0


def load_price_data(
    *,
    prices_path: str | Path | None = None,
    tickers: list[str] | None = None,
    download: bool = False,
    download_period: str = "10y",
) -> pd.DataFrame:
    if download:
        if not tickers:
            raise ValueError("tickers are required when download=True")
        prices = download_prices(tickers, period=download_period)
    elif prices_path:
        prices = read_table(prices_path)
    else:
        raise ValueError("Either prices_path or download=True is required.")
    return to_long_ohlcv(prices)


def future_return(close: np.ndarray, start_idx: int, horizon: int) -> float:
    end_idx = start_idx + horizon
    if start_idx < 0 or end_idx >= len(close):
        return np.nan
    start = close[start_idx]
    end = close[end_idx]
    if start == 0 or np.isnan(start) or np.isnan(end):
        return np.nan
    return float(end / start - 1.0)


def forward_max_drawdown(close: np.ndarray, start_idx: int, horizon: int) -> float:
    end_idx = min(start_idx + horizon, len(close) - 1)
    if start_idx < 0 or end_idx <= start_idx:
        return np.nan
    start = close[start_idx]
    if start == 0 or np.isnan(start):
        return np.nan
    path = close[start_idx : end_idx + 1]
    if len(path) == 0:
        return np.nan
    return float(np.nanmin(path / start - 1.0))


def build_outcome_labels(
    *,
    signals_path: str | Path,
    prices_path: str | Path | None,
    out_path: str | Path,
    ticker_col: str | None = None,
    date_col: str | None = None,
    horizons: tuple[int, ...] = (5, 20),
    success_horizon: int = 20,
    success_return_threshold: float = 0.0,
    download_prices_flag: bool = False,
    download_period: str = "10y",
) -> pd.DataFrame:
    signals = read_table(signals_path).copy()
    ticker = detect_ticker_column(signals, ticker_col)
    date = detect_date_column(signals, date_col)
    if date is None:
        raise ValueError("Could not detect signal date column.")

    signals["_calib_ticker"] = signals[ticker].astype(str).str.upper()
    signals["_calib_date"] = pd.to_datetime(signals[date], errors="coerce")
    tickers = sorted(signals["_calib_ticker"].dropna().unique().tolist())

    prices = load_price_data(
        prices_path=prices_path,
        tickers=tickers,
        download=download_prices_flag,
        download_period=download_period,
    )
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices = prices.dropna(subset=["date", "ticker", "close"]).sort_values(["ticker", "date"])

    price_groups = {
        symbol: group[["date", "close"]].dropna().sort_values("date").reset_index(drop=True)
        for symbol, group in prices.groupby("ticker")
    }

    out = signals.copy()
    for horizon in horizons:
        out[f"next_{horizon}d_return"] = np.nan
        out[f"max_drawdown_next_{horizon}d"] = np.nan

    for idx, row in out.iterrows():
        symbol = row["_calib_ticker"]
        signal_date = row["_calib_date"]
        group = price_groups.get(symbol)
        if group is None or pd.isna(signal_date):
            continue
        dates = group["date"].to_numpy(dtype="datetime64[ns]")
        close = group["close"].to_numpy(dtype=float)
        start_idx = int(np.searchsorted(dates, np.datetime64(signal_date), side="left"))
        if start_idx >= len(close):
            continue
        for horizon in horizons:
            out.at[idx, f"next_{horizon}d_return"] = future_return(close, start_idx, horizon)
            out.at[idx, f"max_drawdown_next_{horizon}d"] = forward_max_drawdown(close, start_idx, horizon)

    success_col = f"next_{success_horizon}d_return"
    if success_col in out.columns:
        out["signal_success"] = out[success_col].ge(success_return_threshold).astype("float")
        out.loc[out[success_col].isna(), "signal_success"] = np.nan

    out = out.drop(columns=["_calib_ticker", "_calib_date"])
    write_table(out, out_path)
    return out
