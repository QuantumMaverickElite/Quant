from __future__ import annotations

from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo
import math
import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table type: {path}")


def _prep_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"ticker", "date", "close"}
    missing = sorted(required - set(prices.columns))
    if missing:
        raise ValueError(f"price table missing required columns: {missing}")

    out = prices.copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out[out["date"].notna() & out["close"].notna()].copy()
    out = out.sort_values(["ticker", "date"])
    out = out.drop_duplicates(["ticker", "date"], keep="last")
    return out


def _candidate_base_date(
    event_time: object,
    *,
    market_timezone: str = "America/New_York",
    close_hour: int = 16,
) -> tuple[pd.Timestamp | pd.NaT, str, bool]:
    ts = pd.to_datetime(event_time, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT, "", False

    local = ts.tz_convert(ZoneInfo(market_timezone))
    after_close = (local.hour, local.minute, local.second) >= (close_hour, 0, 0)

    base_day = local.date()
    if after_close:
        base_day = base_day + timedelta(days=1)

    return pd.Timestamp(base_day), local.isoformat(), after_close


def _empty_labels(row: pd.Series, horizons: tuple[int, ...], benchmark_ticker: str) -> dict:
    new = row.to_dict()
    for h in horizons:
        new[f"event_base_date_{h}d"] = pd.NA
        new[f"event_close_{h}d_base"] = pd.NA
        new[f"forward_date_{h}d"] = pd.NA
        new[f"forward_close_{h}d"] = pd.NA
        new[f"forward_return_{h}d"] = pd.NA
        new[f"forward_alpha_vs_{benchmark_ticker.lower()}_{h}d"] = pd.NA
        new[f"forward_drawdown_{h}d"] = pd.NA
        new[f"forward_volatility_{h}d"] = pd.NA
    return new


def _label_one_horizon(
    *,
    px: pd.DataFrame,
    idx: int,
    horizon: int,
    benchmark: pd.DataFrame | None,
    benchmark_ticker: str,
) -> dict:
    new = {}

    base_date = px.loc[idx, "date"]
    base_close = float(px.loc[idx, "close"])

    target_idx = idx + horizon
    if target_idx >= len(px) or not base_close:
        new[f"event_base_date_{horizon}d"] = base_date
        new[f"event_close_{horizon}d_base"] = base_close
        new[f"forward_date_{horizon}d"] = pd.NA
        new[f"forward_close_{horizon}d"] = pd.NA
        new[f"forward_return_{horizon}d"] = pd.NA
        new[f"forward_alpha_vs_{benchmark_ticker.lower()}_{horizon}d"] = pd.NA
        new[f"forward_drawdown_{horizon}d"] = pd.NA
        new[f"forward_volatility_{horizon}d"] = pd.NA
        return new

    target_date = px.loc[target_idx, "date"]
    target_close = float(px.loc[target_idx, "close"])
    fwd_ret = target_close / base_close - 1.0

    window = px.iloc[idx : target_idx + 1].copy()
    rel = window["close"] / base_close - 1.0
    drawdown = float(rel.min()) if len(rel) else math.nan

    daily = window["close"].pct_change().dropna()
    volatility = float(daily.std() * math.sqrt(252)) if len(daily) >= 2 else math.nan

    alpha = pd.NA
    if benchmark is not None:
        b_idx = benchmark["date"].searchsorted(base_date, side="left")
        if b_idx < len(benchmark) and benchmark.loc[b_idx, "date"] == base_date:
            b_target_idx = benchmark["date"].searchsorted(target_date, side="left")
            if b_target_idx < len(benchmark) and benchmark.loc[b_target_idx, "date"] == target_date:
                b_base = float(benchmark.loc[b_idx, "close"])
                b_target = float(benchmark.loc[b_target_idx, "close"])
                if b_base:
                    alpha = fwd_ret - (b_target / b_base - 1.0)

    new[f"event_base_date_{horizon}d"] = base_date
    new[f"event_close_{horizon}d_base"] = base_close
    new[f"forward_date_{horizon}d"] = target_date
    new[f"forward_close_{horizon}d"] = target_close
    new[f"forward_return_{horizon}d"] = fwd_ret
    new[f"forward_alpha_vs_{benchmark_ticker.lower()}_{horizon}d"] = alpha
    new[f"forward_drawdown_{horizon}d"] = drawdown
    new[f"forward_volatility_{horizon}d"] = volatility
    return new


def label_event_outcomes(
    *,
    events_path: str | Path,
    prices_path: str | Path,
    horizons: tuple[int, ...] = (1, 5, 20),
    benchmark_ticker: str = "SPY",
    market_timezone: str = "America/New_York",
    close_hour: int = 16,
) -> pd.DataFrame:
    events = read_table(events_path).copy()
    prices = _prep_prices(read_table(prices_path))

    required = {"event_id", "ticker", "event_time"}
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError(f"event table missing required columns: {missing}")

    events["ticker"] = events["ticker"].astype(str).str.upper()
    events["event_time"] = pd.to_datetime(events["event_time"], errors="coerce", utc=True)

    by_ticker = {
        ticker: g.reset_index(drop=True)
        for ticker, g in prices.groupby("ticker", sort=False)
    }

    benchmark_ticker = benchmark_ticker.upper()
    benchmark = by_ticker.get(benchmark_ticker)

    rows = []

    for _, row in events.iterrows():
        ticker = row["ticker"]
        px = by_ticker.get(ticker)

        candidate_date, event_local_time, after_close = _candidate_base_date(
            row["event_time"],
            market_timezone=market_timezone,
            close_hour=close_hour,
        )

        row = row.copy()
        row["event_local_time"] = event_local_time
        row["event_after_market_close"] = after_close
        row["label_candidate_date"] = candidate_date

        if px is None or pd.isna(candidate_date) or len(px) == 0:
            rows.append(_empty_labels(row, horizons, benchmark_ticker))
            continue

        first_date = px["date"].iloc[0]
        last_date = px["date"].iloc[-1]

        if candidate_date < first_date or candidate_date > last_date:
            rows.append(_empty_labels(row, horizons, benchmark_ticker))
            continue

        idx = px["date"].searchsorted(candidate_date, side="left")
        if idx >= len(px):
            rows.append(_empty_labels(row, horizons, benchmark_ticker))
            continue

        new = row.to_dict()
        for h in horizons:
            new.update(
                _label_one_horizon(
                    px=px,
                    idx=idx,
                    horizon=h,
                    benchmark=benchmark,
                    benchmark_ticker=benchmark_ticker,
                )
            )

        rows.append(new)

    return pd.DataFrame(rows)


def write_labeled_events(df: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".parquet":
        df.to_parquet(out_path, index=False)
        df.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".csv":
        df.to_csv(out_path, index=False)
        df.to_parquet(out_path.with_suffix(".parquet"), index=False)
    else:
        raise ValueError(f"Unsupported output type: {out_path}")
