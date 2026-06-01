# src/backtester/correlation/io.py

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from backtester.correlation.types import AssetMetadata, ReturnMatrix


def prices_to_return_matrix(
    prices: pd.DataFrame,
    *,
    tickers: Sequence[str] | None = None,
    log_returns: bool = False,
    min_non_nan_fraction: float = 0.90,
    dtype: type = np.float32,
) -> ReturnMatrix:
    """
    Convert an adjusted-close price DataFrame into a clean ReturnMatrix.

    Expected input:
        index = dates
        columns = tickers
        values = adjusted close prices

    This function:
        - sorts dates
        - optionally selects tickers
        - removes tickers with too much missing data
        - forward-fills small gaps
        - calculates returns
        - replaces inf values with nan
        - drops rows where all returns are missing
    """

    if prices.empty:
        raise ValueError("prices DataFrame is empty.")

    frame = prices.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    if tickers is not None:
        missing = [ticker for ticker in tickers if ticker not in frame.columns]
        if missing:
            raise ValueError(f"Missing tickers in prices DataFrame: {missing}")

        frame = frame.loc[:, list(tickers)]

    non_nan_fraction = frame.notna().mean(axis=0)
    keep_cols = non_nan_fraction[non_nan_fraction >= min_non_nan_fraction].index

    frame = frame.loc[:, keep_cols]

    if frame.empty:
        raise ValueError("No tickers survived the missing-data filter.")

    frame = frame.ffill()

    if log_returns:
        returns = np.log(frame / frame.shift(1))
    else:
        returns = frame.pct_change(fill_method=None)

    returns = returns.replace([np.inf, -np.inf], np.nan)
    returns = returns.dropna(axis=0, how="all")

    # Fill remaining isolated missing returns with 0 for matrix compatibility.
    # Later we can make this stricter or add masks.
    returns = returns.fillna(0.0)

    return_matrix = ReturnMatrix(
        values=returns.to_numpy(dtype=dtype),
        dates=pd.DatetimeIndex(returns.index),
        tickers=list(returns.columns),
    )

    return_matrix.validate()
    return return_matrix


def build_asset_metadata(
    tickers: Sequence[str],
    sectors: Mapping[str, str] | None = None,
    industries: Mapping[str, str] | None = None,
) -> AssetMetadata:
    """
    Build integer sector/industry code arrays aligned to tickers.

    Missing values receive code -1.
    """

    sectors = sectors or {}
    industries = industries or {}

    sector_labels = [sectors.get(ticker, None) for ticker in tickers]
    industry_labels = [industries.get(ticker, None) for ticker in tickers]

    sector_codes = _labels_to_codes(sector_labels)
    industry_codes = _labels_to_codes(industry_labels)

    metadata = AssetMetadata(
        tickers=list(tickers),
        sector_codes=sector_codes,
        industry_codes=industry_codes,
    )

    metadata.validate()
    return metadata


def _labels_to_codes(labels: Sequence[str | None]) -> np.ndarray:
    codes = np.full(len(labels), -1, dtype=np.int32)

    known_labels = sorted({label for label in labels if label is not None})
    mapping = {label: i for i, label in enumerate(known_labels)}

    for i, label in enumerate(labels):
        if label is not None:
            codes[i] = mapping[label]

    return codes
