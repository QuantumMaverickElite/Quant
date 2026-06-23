from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


NON_PRICE_TOPICS = {
    "MARKET",
    "MACRO",
    "ECONOMY",
    "ECONOMIC",
    "POLITICS",
    "POLITICAL",
    "RATES",
    "FED",
    "FOMC",
    "INFLATION",
    "YIELDS",
}


@dataclass(slots=True)
class PriceRiskRow:
    query: str
    peer_divergence: float
    volume_shock: float
    trend_damage: float
    latest_close: float
    recent_return: float
    benchmark_return: float
    peer_return: float


def clamp01(x: float) -> float:
    if np.isnan(x) or np.isinf(x):
        return 0.0
    return float(max(0.0, min(1.0, x)))


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def load_price_frame(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    return normalize_columns(df)


def load_peer_map(path: str | Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}

    peers: dict[str, list[str]] = {}
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            query = (row.get("query") or row.get("ticker") or row.get("symbol") or "").strip().upper()
            if not query:
                continue
            raw_peer = (row.get("peer") or row.get("peers") or "").strip()
            if not raw_peer:
                continue
            parts = [part.strip().upper() for part in raw_peer.replace(";", ",").split(",") if part.strip()]
            peers.setdefault(query, []).extend(parts)
    return {query: sorted(set(values)) for query, values in peers.items()}


def is_price_ticker(query: str) -> bool:
    query = query.strip().upper()
    if query in NON_PRICE_TOPICS:
        return False
    return bool(query) and all(ch.isalnum() or ch in {".", "-", "^"} for ch in query)


def download_ticker_universe(
    queries: list[str],
    *,
    benchmark: str,
    peer_map: dict[str, list[str]],
) -> list[str]:
    tickers: set[str] = {benchmark.upper()}
    tickers.update(query.upper() for query in queries if is_price_ticker(query))
    for peers in peer_map.values():
        tickers.update(peer.upper() for peer in peers if is_price_ticker(peer))
    return sorted(tickers)


def download_prices(tickers: list[str], period: str = "6mo") -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("yfinance is required for --download. Install it or pass --prices.") from exc

    data = yf.download(
        tickers=sorted(set(tickers)),
        period=period,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if data.empty:
        raise SystemExit("No price data returned by yfinance.")

    rows: list[pd.DataFrame] = []
    if isinstance(data.columns, pd.MultiIndex):
        for ticker in sorted(set(tickers)):
            if ticker not in data.columns.get_level_values(0):
                continue
            sub = data[ticker].reset_index()
            if sub.empty:
                continue
            sub["ticker"] = ticker
            rows.append(sub)
    else:
        sub = data.reset_index()
        if sub.empty:
            raise SystemExit("No usable price rows returned by yfinance.")
        sub["ticker"] = tickers[0]
        rows.append(sub)

    if not rows:
        raise SystemExit("No usable price rows returned by yfinance.")

    out = pd.concat(rows, ignore_index=True)
    return normalize_columns(out)


def to_long_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    if {"date", "ticker"}.issubset(df.columns):
        close_col = first_existing(df, ["adj close", "adj_close", "close"])
        volume_col = first_existing(df, ["volume"])
        cols = ["date", "ticker", close_col]
        if volume_col:
            cols.append(volume_col)
        out = df[cols].copy()
        out = out.rename(columns={close_col: "close"})
        if volume_col:
            out = out.rename(columns={volume_col: "volume"})
        else:
            out["volume"] = np.nan
        out["ticker"] = out["ticker"].astype(str).str.upper()
        out["date"] = pd.to_datetime(out["date"])
        return out.sort_values(["ticker", "date"])

    date_col = first_existing(df, ["date", "datetime", "timestamp"])
    if not date_col:
        raise ValueError("Price file must be long format or wide format with a date column.")

    value_cols = [col for col in df.columns if col != date_col]
    wide = df[[date_col, *value_cols]].copy()
    wide[date_col] = pd.to_datetime(wide[date_col])
    out = wide.melt(id_vars=[date_col], var_name="ticker", value_name="close")
    out = out.rename(columns={date_col: "date"})
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["volume"] = np.nan
    return out.dropna(subset=["close"]).sort_values(["ticker", "date"])


def first_existing(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def pct_return(close: pd.Series, lookback: int) -> float:
    close = close.dropna()
    if len(close) < 2:
        return 0.0
    window = min(lookback, len(close) - 1)
    prev = close.iloc[-window - 1]
    latest = close.iloc[-1]
    if prev == 0 or np.isnan(prev):
        return 0.0
    return float(latest / prev - 1.0)


def compute_volume_shock(volume: pd.Series, window: int = 20) -> float:
    volume = volume.dropna()
    if len(volume) < max(5, window):
        return 0.0
    baseline = volume.iloc[-window:-1].median()
    if baseline <= 0 or np.isnan(baseline):
        return 0.0
    ratio = float(volume.iloc[-1] / baseline)
    return clamp01((ratio - 1.0) / 3.0)


def compute_trend_damage(close: pd.Series, short_window: int = 20, long_window: int = 50) -> float:
    close = close.dropna()
    if len(close) < 5:
        return 0.0

    latest = float(close.iloc[-1])
    recent_high = float(close.tail(min(60, len(close))).max())
    drawdown = 0.0 if recent_high <= 0 else max(0.0, 1.0 - latest / recent_high)

    short_ma = close.tail(min(short_window, len(close))).mean()
    long_ma = close.tail(min(long_window, len(close))).mean()
    ma_damage = 0.0 if long_ma <= 0 else max(0.0, 1.0 - short_ma / long_ma)

    recent_return = pct_return(close, min(20, len(close) - 1))
    momentum_damage = max(0.0, -recent_return)

    return clamp01(2.5 * drawdown + 3.0 * ma_damage + 1.5 * momentum_damage)


def average_available(values: list[float]) -> float:
    valid = [value for value in values if not np.isnan(value)]
    if not valid:
        return 0.0
    return float(np.nanmean(valid))


def empty_price_risk_row(query: str, benchmark_return: float = 0.0, peer_return: float | None = None) -> PriceRiskRow:
    return PriceRiskRow(
        query=query.upper(),
        peer_divergence=0.0,
        volume_shock=0.0,
        trend_damage=0.0,
        latest_close=0.0,
        recent_return=round(float(peer_return if peer_return is not None else 0.0), 6),
        benchmark_return=round(float(benchmark_return), 6),
        peer_return=round(float(peer_return if peer_return is not None else benchmark_return), 6),
    )


def compute_peer_divergence(
    query_return: float,
    benchmark_return: float,
    peer_return: float,
    *,
    scale: float = 0.15,
) -> float:
    reference = peer_return if not np.isnan(peer_return) else benchmark_return
    underperformance = reference - query_return
    return clamp01(underperformance / scale)


def build_price_risk_features(
    prices: pd.DataFrame,
    queries: list[str],
    *,
    benchmark: str = "QQQ",
    peer_map: dict[str, list[str]] | None = None,
    lookback: int = 20,
) -> list[PriceRiskRow]:
    long_df = to_long_ohlcv(prices)
    peer_map = peer_map or {}
    grouped = {ticker: sub.sort_values("date") for ticker, sub in long_df.groupby("ticker")}
    benchmark = benchmark.upper()
    benchmark_return = pct_return(grouped[benchmark]["close"], lookback) if benchmark in grouped else 0.0

    rows: list[PriceRiskRow] = []
    for query in queries:
        query = query.upper()
        peers = [peer for peer in peer_map.get(query, []) if peer in grouped and peer != query]

        if query not in grouped or grouped[query]["close"].dropna().empty:
            if peers:
                peer_returns = [pct_return(grouped[peer]["close"], lookback) for peer in peers]
                peer_volumes = [compute_volume_shock(grouped[peer]["volume"]) for peer in peers]
                peer_trends = [compute_trend_damage(grouped[peer]["close"]) for peer in peers]
                peer_return = average_available(peer_returns)
                row = empty_price_risk_row(query, benchmark_return=benchmark_return, peer_return=peer_return)
                row.volume_shock = round(average_available(peer_volumes), 4)
                row.trend_damage = round(average_available(peer_trends), 4)
                rows.append(row)
            else:
                rows.append(empty_price_risk_row(query, benchmark_return=benchmark_return))
            continue

        sub = grouped[query]
        query_return = pct_return(sub["close"], lookback)
        if peers:
            peer_returns = [pct_return(grouped[peer]["close"], lookback) for peer in peers]
            peer_return = float(np.nanmean(peer_returns))
        else:
            peer_return = benchmark_return

        rows.append(
            PriceRiskRow(
                query=query,
                peer_divergence=round(compute_peer_divergence(query_return, benchmark_return, peer_return), 4),
                volume_shock=round(compute_volume_shock(sub["volume"]), 4),
                trend_damage=round(compute_trend_damage(sub["close"]), 4),
                latest_close=round(float(sub["close"].dropna().iloc[-1]), 4),
                recent_return=round(query_return, 6),
                benchmark_return=round(benchmark_return, 6),
                peer_return=round(peer_return, 6),
            )
        )
    return rows


def write_price_risk_csv(rows: list[PriceRiskRow], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query",
        "peer_divergence",
        "volume_shock",
        "trend_damage",
        "latest_close",
        "recent_return",
        "benchmark_return",
        "peer_return",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fieldnames})
