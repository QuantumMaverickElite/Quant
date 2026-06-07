#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Augment market graph frames with compact trade overlay arrays."
    )
    p.add_argument(
        "--frames-dir", required=True, help="Base market graph frames directory"
    )
    p.add_argument(
        "--trade-overlay", required=True, help="trade_visual_overlay.parquet"
    )
    p.add_argument(
        "--portfolio-overlay", required=True, help="portfolio_visual_overlay.parquet"
    )
    p.add_argument("--out-dir", required=True, help="Augmented output directory")
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def load_ticks_from_frame(npz_path: Path):
    data = np.load(npz_path, allow_pickle=True)
    keys = list(data.keys())

    ticker_key = None
    for k in ["tickers", "ticker", "symbols", "symbol"]:
        if k in keys:
            ticker_key = k
            break
    if ticker_key is None:
        raise ValueError(f"Could not find ticker array in {npz_path}. Keys: {keys}")

    tickers = data[ticker_key]
    if isinstance(tickers, np.ndarray):
        tickers = [str(x) for x in tickers.tolist()]
    else:
        tickers = [str(x) for x in tickers]

    payload = {k: data[k] for k in keys}
    return tickers, payload


def main() -> None:
    args = parse_args()

    frames_dir = Path(args.frames_dir)
    out_dir = Path(args.out_dir)
    trade_overlay = pd.read_parquet(args.trade_overlay)
    portfolio_overlay = pd.read_parquet(args.portfolio_overlay)

    frame_summary_path = frames_dir / "frame_summary.csv"
    manifest_path = frames_dir / "manifest.json"
    frames_npz_dir = frames_dir / "frames"

    if not frame_summary_path.exists():
        raise FileNotFoundError(frame_summary_path)
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if not frames_npz_dir.exists():
        raise FileNotFoundError(frames_npz_dir)

    if out_dir.exists():
        if not args.force:
            raise FileExistsError(f"{out_dir} exists; use --force")
        shutil.rmtree(out_dir)

    (out_dir / "frames").mkdir(parents=True, exist_ok=True)

    frame_summary = pd.read_csv(frame_summary_path)
    frame_summary["date"] = pd.to_datetime(frame_summary["date"]).dt.normalize()

    trade_overlay["date"] = pd.to_datetime(trade_overlay["date"]).dt.normalize()
    portfolio_overlay["date"] = pd.to_datetime(portfolio_overlay["date"]).dt.normalize()

    report_rows = []

    for i, row in frame_summary.reset_index(drop=True).iterrows():
        frame_date = pd.Timestamp(row["date"]).normalize()
        frame_name = f"frame_{i:04d}.npz"
        in_path = frames_npz_dir / frame_name
        out_path = out_dir / "frames" / frame_name

        tickers, payload = load_ticks_from_frame(in_path)

        day_trade = trade_overlay[trade_overlay["date"] == frame_date].copy()
        day_port = portfolio_overlay[portfolio_overlay["date"] == frame_date].copy()

        if len(day_trade):
            day_trade = day_trade.set_index("ticker")
        else:
            day_trade = pd.DataFrame(index=[])

        n = len(tickers)

        def build_array(col, default, dtype):
            vals = []
            for t in tickers:
                if t in day_trade.index and col in day_trade.columns:
                    vals.append(day_trade.loc[t, col])
                else:
                    vals.append(default)
            return np.asarray(vals, dtype=dtype)

        payload["trade_is_active"] = build_array("is_active_trade", False, np.bool_)
        payload["trade_active_count"] = build_array("active_trade_count", 0, np.int16)
        payload["trade_opened_today"] = build_array("opened_today_count", 0, np.int16)
        payload["trade_closed_today"] = build_array("closed_today_count", 0, np.int16)
        payload["trade_unrealized_pnl"] = build_array("unrealized_pnl", 0.0, np.float32)
        payload["trade_realized_pnl_today"] = build_array(
            "realized_pnl_today", 0.0, np.float32
        )
        payload["trade_open_entry_value"] = build_array(
            "open_entry_value", 0.0, np.float32
        )
        payload["trade_current_value"] = build_array("current_value", 0.0, np.float32)
        payload["trade_open_return"] = build_array(
            "avg_open_trade_return", 0.0, np.float32
        )
        payload["trade_avg_confidence"] = build_array(
            "avg_adjusted_confidence", 0.0, np.float32
        )

        if len(day_port):
            port = day_port.iloc[0]
            payload["portfolio_equity"] = np.asarray(
                [port.get("equity", np.nan)], dtype=np.float32
            )
            payload["portfolio_drawdown"] = np.asarray(
                [port.get("drawdown", np.nan)], dtype=np.float32
            )
            payload["portfolio_open_trades"] = np.asarray(
                [port.get("open_trades", 0)], dtype=np.int32
            )
            payload["portfolio_active_tickers"] = np.asarray(
                [port.get("active_tickers", 0)], dtype=np.int32
            )
            payload["portfolio_realized_pnl_today"] = np.asarray(
                [port.get("realized_pnl_today", 0.0)], dtype=np.float32
            )
            payload["portfolio_realized_pnl_cum"] = np.asarray(
                [port.get("realized_pnl_cum", 0.0)], dtype=np.float32
            )
            payload["portfolio_unrealized_pnl"] = np.asarray(
                [port.get("unrealized_pnl", 0.0)], dtype=np.float32
            )
        else:
            payload["portfolio_equity"] = np.asarray([np.nan], dtype=np.float32)
            payload["portfolio_drawdown"] = np.asarray([np.nan], dtype=np.float32)
            payload["portfolio_open_trades"] = np.asarray([0], dtype=np.int32)
            payload["portfolio_active_tickers"] = np.asarray([0], dtype=np.int32)
            payload["portfolio_realized_pnl_today"] = np.asarray(
                [0.0], dtype=np.float32
            )
            payload["portfolio_realized_pnl_cum"] = np.asarray([0.0], dtype=np.float32)
            payload["portfolio_unrealized_pnl"] = np.asarray([0.0], dtype=np.float32)

        np.savez_compressed(out_path, **payload)

        matched = int(
            payload["trade_is_active"].sum()
            + (payload["trade_opened_today"] > 0).sum()
            + (payload["trade_closed_today"] > 0).sum()
        )
        report_rows.append(
            {
                "frame": frame_name,
                "date": frame_date,
                "nodes": n,
                "active_nodes": int(payload["trade_is_active"].sum()),
                "opened_today_nodes": int((payload["trade_opened_today"] > 0).sum()),
                "closed_today_nodes": int((payload["trade_closed_today"] > 0).sum()),
                "match_score": matched,
            }
        )
        print(
            f"[{i+1:04d}/{len(frame_summary):04d}] {frame_date.date()} active={int(payload['trade_is_active'].sum())} opened={int((payload['trade_opened_today'] > 0).sum())} closed={int((payload['trade_closed_today'] > 0).sum())}"
        )

    shutil.copy2(frame_summary_path, out_dir / "frame_summary.csv")
    shutil.copy2(manifest_path, out_dir / "manifest.json")
    shutil.copy2(args.trade_overlay, out_dir / "trade_visual_overlay.parquet")
    shutil.copy2(args.portfolio_overlay, out_dir / "portfolio_visual_overlay.parquet")

    report = pd.DataFrame(report_rows)
    report_path = out_dir / "trade_overlay_augmentation_report.csv"
    report.to_csv(report_path, index=False)

    print()
    print(f"Saved augmented frames -> {out_dir}")
    print(f"Saved report -> {report_path}")
    print()
    print(report.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
