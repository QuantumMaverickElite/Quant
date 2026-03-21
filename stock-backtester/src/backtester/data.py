import pandas as pd
import yfinance as yf


def fetch_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [c.lower().strip() for c in df.columns]
    if "close" not in df.columns:
        raise ValueError(f"Available columns: {list(df.columns)}")

    return df

def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    if df.empty:
        raise ValueError(f"No OHLCV data returned for {ticker}")

    return df


def fetch_dividends(ticker: str, start: str, end: str) -> pd.Series:
    dividends = yf.Ticker(ticker).dividends
    if dividends is None or len(dividends) == 0:
        return pd.Series(dtype=float)

    dividends = dividends.copy()
    dividends.index = pd.to_datetime(dividends.index)
    if getattr(dividends.index, "tz", None) is not None:
        dividends.index = dividends.index.tz_localize(None)

    dividends = dividends.sort_index()
    dividends = dividends[
        (dividends.index >= pd.Timestamp(start)) &
        (dividends.index < pd.Timestamp(end))
    ]

    return dividends
