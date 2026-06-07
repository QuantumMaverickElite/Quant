#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build compact trade + portfolio overlays for market fabric frames."
    )
    p.add_argument("--closed-trades", required=True, help="actual_closed_trades.csv")
    p.add_argument("--actual-equity", required=True, help="actual_equity.csv")
    p.add_argument(
        "--frame-summary",
        required=True,
        help="frame_summary.csv from market fabric build",
    )
    p.add_argument(
        "--prices-meta", required=True, help="prices_meta.json for current-price lookup"
    )
    p.add_argument("--out-dir", required=True, help="Output directory")
    p.add_argument("--top", type=int, default=20, help="Rows to print in preview")
    return p.parse_args()


def load_price_matrix(meta_path: Path):
    meta = json.loads(meta_path.read_text())
    rows = int(meta["rows"])
    cols = int(meta["cols"])
    dtype = np.dtype(meta["dtype"])
    bin_path = meta_path.parent / meta["binary_file"]

    tickers = meta.get("tickers") or meta.get("columns")
    dates = pd.to_datetime(meta.get("dates") or meta.get("index")).normalize()

    arr = np.memmap(bin_path, dtype=dtype, mode="r", shape=(rows, cols))
    ticker_to_col = {t: i for i, t in enumerate(tickers)}
    date_to_row = {pd.Timestamp(d).normalize(): i for i, d in enumerate(dates)}
    return arr, ticker_to_col, date_to_row


def find_date_col(df: pd.DataFrame) -> str:
    candidates = ["date", "Date", "timestamp", "dt"]
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"Could not find date column. Columns: {list(df.columns)}")


def find_equity_col(df: pd.DataFrame) -> str:
    candidates = ["equity", "portfolio_equity", "account_equity", "total_equity"]
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"Could not find equity column. Columns: {list(df.columns)}")


def find_drawdown_col(df: pd.DataFrame) -> Optional[str]:
    candidates = ["drawdown", "max_drawdown", "portfolio_drawdown"]
    for c in candidates:
        if c in df.columns:
            return c
    return None


def current_trade_factor(
    direction: str, current_price: float, entry_price: float
) -> float:
    if (
        not np.isfinite(current_price)
        or not np.isfinite(entry_price)
        or entry_price <= 0
    ):
        return np.nan
    if str(direction).lower() == "short":
        # simple symmetric approximation for now
        return 2.0 - (current_price / entry_price)
    return current_price / entry_price


def main() -> None:
    args = parse_args()

    closed_trades_path = Path(args.closed_trades)
    actual_equity_path = Path(args.actual_equity)
    frame_summary_path = Path(args.frame_summary)
    prices_meta_path = Path(args.prices_meta)
    out_dir = Path(args.out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(closed_trades_path)
    equity = pd.read_csv(actual_equity_path)
    frame_summary = pd.read_csv(frame_summary_path)

    for c in ["signal_date", "entry_date", "exit_date"]:
        trades[c] = pd.to_datetime(trades[c]).dt.normalize()

    frame_summary["date"] = pd.to_datetime(frame_summary["date"]).dt.normalize()
    frame_dates = pd.Series(
        sorted(frame_summary["date"].dropna().unique())
    ).dt.normalize()

    eq_date_col = find_date_col(equity)
    eq_equity_col = find_equity_col(equity)
    eq_drawdown_col = find_drawdown_col(equity)

    equity[eq_date_col] = pd.to_datetime(equity[eq_date_col]).dt.normalize()
    equity = equity.sort_values(eq_date_col).reset_index(drop=True)

    price_arr, ticker_to_col, date_to_row = load_price_matrix(prices_meta_path)

    trade_rows = []
    portfolio_rows = []

    realized_pnl_cum = 0.0

    for frame_date in frame_dates:
        frame_date = pd.Timestamp(frame_date).normalize()

        opened_today = trades[trades["entry_date"] == frame_date].copy()
        closed_today = trades[trades["exit_date"] == frame_date].copy()
        active = trades[
            (trades["entry_date"] <= frame_date) & (trades["exit_date"] > frame_date)
        ].copy()

        realized_pnl_today = (
            float(closed_today["pnl"].sum()) if len(closed_today) else 0.0
        )
        realized_pnl_cum += realized_pnl_today

        if len(active):
            row_idx = date_to_row.get(frame_date, None)
            current_prices = []
            for _, r in active.iterrows():
                col_idx = ticker_to_col.get(r["ticker"], None)
                if row_idx is None or col_idx is None:
                    current_prices.append(np.nan)
                else:
                    current_prices.append(float(price_arr[row_idx, col_idx]))
            active["current_price"] = current_prices

            factors = [
                current_trade_factor(d, cp, ep)
                for d, cp, ep in zip(
                    active["direction"], active["current_price"], active["entry_price"]
                )
            ]
            active["current_factor"] = factors
            active["current_value"] = active["entry_value"] * active["current_factor"]
            active["unrealized_pnl"] = active["current_value"] - active["entry_value"]
            active["open_trade_return"] = active["current_factor"] - 1.0
        else:
            active["current_price"] = []
            active["current_factor"] = []
            active["current_value"] = []
            active["unrealized_pnl"] = []
            active["open_trade_return"] = []

        active_agg = pd.DataFrame()
        if len(active):
            active_agg = active.groupby("ticker", as_index=False).agg(
                active_trade_count=("ticker", "size"),
                open_entry_value=("entry_value", "sum"),
                current_value=("current_value", "sum"),
                unrealized_pnl=("unrealized_pnl", "sum"),
                avg_open_trade_return=("open_trade_return", "mean"),
                avg_adjusted_confidence=("adjusted_confidence", "mean"),
                avg_peer_spread_z=("peer_spread_z", "mean"),
            )
            active_agg["is_active_trade"] = True

        opened_agg = pd.DataFrame()
        if len(opened_today):
            opened_agg = opened_today.groupby("ticker", as_index=False).agg(
                opened_today_count=("ticker", "size")
            )

        closed_agg = pd.DataFrame()
        if len(closed_today):
            closed_agg = closed_today.groupby("ticker", as_index=False).agg(
                closed_today_count=("ticker", "size"),
                realized_pnl_today=("pnl", "sum"),
                avg_closed_trade_return=("trade_return", "mean"),
            )

        ticker_overlay = pd.DataFrame({"ticker": pd.Series(dtype=str)})

        parts = [df for df in [active_agg, opened_agg, closed_agg] if len(df)]
        if parts:
            ticker_overlay = parts[0]
            for part in parts[1:]:
                ticker_overlay = ticker_overlay.merge(part, on="ticker", how="outer")

        if len(ticker_overlay):
            ticker_overlay["date"] = frame_date
            for c in [
                "active_trade_count",
                "opened_today_count",
                "closed_today_count",
            ]:
                if c not in ticker_overlay.columns:
                    ticker_overlay[c] = 0
                ticker_overlay[c] = ticker_overlay[c].fillna(0).astype(np.int16)

            for c in [
                "open_entry_value",
                "current_value",
                "unrealized_pnl",
                "realized_pnl_today",
                "avg_open_trade_return",
                "avg_adjusted_confidence",
                "avg_peer_spread_z",
                "avg_closed_trade_return",
            ]:
                if c not in ticker_overlay.columns:
                    ticker_overlay[c] = 0.0
                ticker_overlay[c] = ticker_overlay[c].fillna(0.0).astype(np.float32)

            if "is_active_trade" not in ticker_overlay.columns:
                ticker_overlay["is_active_trade"] = False
            ticker_overlay["is_active_trade"] = (
                ticker_overlay["is_active_trade"].fillna(False).astype(bool)
            )

            trade_rows.append(ticker_overlay)

        eq_asof = pd.merge_asof(
            pd.DataFrame({"date": [frame_date]}).sort_values("date"),
            equity[
                [eq_date_col, eq_equity_col]
                + ([eq_drawdown_col] if eq_drawdown_col else [])
            ]
            .rename(columns={eq_date_col: "date"})
            .sort_values("date"),
            on="date",
            direction="backward",
        )

        active_tickers = int(active["ticker"].nunique()) if len(active) else 0
        open_trades = int(len(active))
        unrealized_pnl_total = (
            float(active["unrealized_pnl"].sum()) if len(active) else 0.0
        )

        row = {
            "date": frame_date,
            "equity": (
                float(eq_asof.iloc[0][eq_equity_col])
                if len(eq_asof) and pd.notna(eq_asof.iloc[0][eq_equity_col])
                else np.nan
            ),
            "drawdown": (
                float(eq_asof.iloc[0][eq_drawdown_col])
                if eq_drawdown_col
                and len(eq_asof)
                and pd.notna(eq_asof.iloc[0][eq_drawdown_col])
                else np.nan
            ),
            "open_trades": open_trades,
            "active_tickers": active_tickers,
            "realized_pnl_today": realized_pnl_today,
            "realized_pnl_cum": realized_pnl_cum,
            "unrealized_pnl": unrealized_pnl_total,
        }
        portfolio_rows.append(row)

    trade_overlay = (
        pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    )
    portfolio_overlay = pd.DataFrame(portfolio_rows)

    trade_out = out_dir / "trade_visual_overlay.parquet"
    portfolio_out = out_dir / "portfolio_visual_overlay.parquet"
    trade_latest_csv = out_dir / "trade_visual_overlay_latest.csv"
    portfolio_latest_csv = out_dir / "portfolio_visual_overlay_latest.csv"

    trade_overlay.to_parquet(trade_out, index=False)
    portfolio_overlay.to_parquet(portfolio_out, index=False)

    if len(trade_overlay):
        latest_date = trade_overlay["date"].max()
        latest_trade = trade_overlay[trade_overlay["date"] == latest_date].copy()
        latest_trade = latest_trade.sort_values(
            ["is_active_trade", "unrealized_pnl", "realized_pnl_today"],
            ascending=[False, False, False],
        )
        latest_trade.to_csv(trade_latest_csv, index=False)
    else:
        latest_trade = pd.DataFrame()

    if len(portfolio_overlay):
        latest_port = portfolio_overlay.tail(20).copy()
        latest_port.to_csv(portfolio_latest_csv, index=False)
    else:
        latest_port = pd.DataFrame()

    print(f"Saved trade overlay:     {trade_out}")
    print(f"Saved portfolio overlay: {portfolio_out}")
    print(f"Saved latest trade csv:  {trade_latest_csv}")
    print(f"Saved latest port csv:   {portfolio_latest_csv}")
    print()

    if len(latest_trade):
        print("Latest trade overlay preview:")
        cols = [
            "date",
            "ticker",
            "is_active_trade",
            "active_trade_count",
            "opened_today_count",
            "closed_today_count",
            "unrealized_pnl",
            "realized_pnl_today",
            "avg_open_trade_return",
            "avg_adjusted_confidence",
        ]
        cols = [c for c in cols if c in latest_trade.columns]
        print(latest_trade[cols].head(args.top).to_string(index=False))
        print()

    if len(portfolio_overlay):
        print("Latest portfolio overlay preview:")
        print(portfolio_overlay.tail(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
