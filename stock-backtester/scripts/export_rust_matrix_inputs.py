# scripts/export_rust_matrix_inputs.py

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Rust-ready binary price matrix and orders."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    parser.add_argument("--out-dir", default="/tmp/quant_rust_matrix/h100")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--signal-horizon", type=int, default=100)
    parser.add_argument("--hold-days", type=int, default=100)
    parser.add_argument("--min-adjusted-confidence", type=float, default=0.10)
    parser.add_argument("--top-n-per-date", type=int, default=5)
    parser.add_argument(
        "--universe-file", default="data/universes/liquid_large_mid.txt"
    )

    parser.add_argument(
        "--dtype",
        choices=["float32", "float64"],
        default="float32",
        help="Matrix dtype. Use float32 for large universes.",
    )

    parser.add_argument(
        "--drop-bad-price-columns",
        action="store_true",
        help="Drop tickers with poor price history after download.",
    )
    parser.add_argument(
        "--min-valid-price-coverage",
        type=float,
        default=0.80,
        help="Minimum fraction of non-missing positive prices required to keep a ticker.",
    )
    parser.add_argument(
        "--max-initial-missing-days",
        type=int,
        default=252,
        help="Maximum allowed missing days from the beginning of the matrix.",
    )
    parser.add_argument(
        "--keep-signal-tickers",
        action="store_true",
        default=True,
        help="Always keep signal tickers if price data exists.",
    )

    parser.add_argument(
        "--download-batch-size",
        type=int,
        default=100,
        help="Number of tickers per yfinance batch.",
    )
    parser.add_argument(
        "--download-sleep-seconds",
        type=float,
        default=2.0,
        help="Sleep between yfinance batches to reduce rate limiting.",
    )
    parser.add_argument(
        "--download-retries",
        type=int,
        default=3,
        help="Number of retries per batch.",
    )
    parser.add_argument(
        "--priority-signal-download",
        action="store_true",
        default=True,
        help="Download signal tickers first so strategy orders are protected.",
    )

    parser.add_argument(
        "--fail-on-missing-signal-tickers",
        action="store_true",
        default=True,
        help="Fail if required signal tickers are missing from the final price matrix.",
    )
    parser.add_argument(
        "--allow-missing-signal-tickers",
        action="store_true",
        help="Allow missing signal tickers. Use only for damaged-data/debug runs.",
    )

    parser.add_argument(
        "--min-exported-orders",
        type=int,
        default=1,
        help="Fail if fewer than this many orders are exported.",
    )
    parser.add_argument(
        "--warn-if-exported-orders-below",
        type=int,
        default=400,
        help="Warn if exported order count falls below this threshold.",
    )

    return parser.parse_args()


def normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".", "-")


def load_universe(path: str) -> list[str]:
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(p)

    tickers = [
        normalize_ticker(line)
        for line in p.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    out: list[str] = []
    seen: set[str] = set()

    for ticker in tickers:
        if ticker and ticker not in seen:
            out.append(ticker)
            seen.add(ticker)

    return out


def chunked(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("--download-batch-size must be positive")

    return [items[i : i + size] for i in range(0, len(items), size)]


def extract_close(data: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            return pd.DataFrame()
        close = data["Close"].copy()
    else:
        if "Close" not in data.columns:
            return pd.DataFrame()

        close = data[["Close"]].copy()

        if len(tickers) == 1:
            close.columns = [tickers[0]]

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()

    close.columns = [normalize_ticker(c) for c in close.columns]
    close = close.loc[:, ~pd.Index(close.columns).duplicated()].copy()
    close = close.dropna(axis=1, how="all")

    return close


def download_one_batch(
    tickers: list[str],
    *,
    start: str,
    end: str | None,
) -> pd.DataFrame:
    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=True,
        group_by="column",
        threads=True,
    )

    return extract_close(data, tickers)


def download_adjusted_close_chunked(
    tickers: list[str],
    *,
    start: str,
    end: str | None,
    batch_size: int,
    sleep_seconds: float,
    retries: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    report_rows: list[dict[str, object]] = []

    batches = chunked(tickers, batch_size)
    total_batches = len(batches)

    print(
        f"Downloading {len(tickers):,} tickers in {total_batches:,} batches of {batch_size:,}..."
    )

    for batch_idx, batch in enumerate(batches, start=1):
        batch = [normalize_ticker(t) for t in batch]
        batch_label = f"{batch_idx}/{total_batches}"

        close = pd.DataFrame()
        error_text = ""

        for attempt in range(1, retries + 1):
            try:
                print()
                print(
                    f"Batch {batch_label}, attempt {attempt}/{retries}, tickers={len(batch)}"
                )
                close = download_one_batch(batch, start=start, end=end)

                if not close.empty:
                    break

                error_text = "empty close dataframe"
            except Exception as exc:
                error_text = repr(exc)
                print(f"Batch {batch_label} failed: {error_text}")

            if attempt < retries:
                time.sleep(sleep_seconds * attempt)

        downloaded = set(close.columns) if not close.empty else set()
        requested = set(batch)
        missing = sorted(requested - downloaded)

        report_rows.append(
            {
                "batch": batch_idx,
                "requested": len(batch),
                "downloaded": len(downloaded),
                "missing": len(missing),
                "missing_tickers": "|".join(missing[:500]),
                "error": error_text,
            }
        )

        if not close.empty:
            frames.append(close)

        if sleep_seconds > 0 and batch_idx < total_batches:
            time.sleep(sleep_seconds)

    if not frames:
        raise RuntimeError("No price data downloaded.")

    prices = pd.concat(frames, axis=1)
    prices = prices.loc[:, ~pd.Index(prices.columns).duplicated()].copy()
    prices = prices.sort_index()

    report = pd.DataFrame(report_rows)

    return prices, report


def signal_candidates(
    signals: pd.DataFrame,
    *,
    signal_horizon: int,
    min_adjusted_confidence: float,
) -> pd.DataFrame:
    frame = signals.copy()
    frame["ticker"] = frame["ticker"].astype(str).map(normalize_ticker)
    frame["date"] = pd.to_datetime(frame["date"])

    frame = frame[
        (frame["horizon"] == signal_horizon)
        & (frame["adjusted_confidence"] >= min_adjusted_confidence)
    ].copy()

    return frame


def required_signal_tickers_for_download(
    signals: pd.DataFrame,
    *,
    signal_horizon: int,
    min_adjusted_confidence: float,
) -> set[str]:
    cand = signal_candidates(
        signals,
        signal_horizon=signal_horizon,
        min_adjusted_confidence=min_adjusted_confidence,
    )

    return set(cand["ticker"])


def retry_missing_signal_tickers(
    prices: pd.DataFrame,
    required_signal_tickers: set[str],
    *,
    start: str,
    end: str | None,
    sleep_seconds: float,
    retries: int,
) -> pd.DataFrame:
    missing = sorted(required_signal_tickers - set(prices.columns))

    if not missing:
        return prices

    print()
    print("=" * 80)
    print("Retrying missing signal tickers separately")
    print("=" * 80)
    print("Missing signal tickers:", " ".join(missing))

    frames = [prices]

    for ticker in missing:
        close = pd.DataFrame()

        for attempt in range(1, retries + 1):
            try:
                print(f"Signal ticker {ticker}, attempt {attempt}/{retries}")
                close = download_one_batch([ticker], start=start, end=end)

                if ticker in close.columns:
                    break
            except Exception as exc:
                print(f"Signal ticker {ticker} failed: {exc!r}")

            if attempt < retries:
                time.sleep(sleep_seconds * attempt)

        if ticker in close.columns:
            frames.append(close[[ticker]])

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    out = pd.concat(frames, axis=1)
    out = out.loc[:, ~pd.Index(out.columns).duplicated()].copy()
    out = out.sort_index()

    return out


def fail_if_missing_signal_tickers(
    prices: pd.DataFrame,
    required_signal_tickers: set[str],
    *,
    fail_on_missing: bool,
    stage: str,
) -> None:
    missing = sorted(required_signal_tickers - set(prices.columns))

    if not missing:
        return

    message = (
        f"Missing required signal tickers from price matrix at stage={stage}:\n"
        + " ".join(missing)
        + "\nThis export may damage the actual strategy. "
        + "Rerun later, reduce universe size, lower batch size, increase sleep, "
        + "or use --allow-missing-signal-tickers explicitly."
    )

    if fail_on_missing:
        raise RuntimeError(message)

    print()
    print("WARNING:", message)


def filter_price_columns(
    prices: pd.DataFrame,
    *,
    required_signal_tickers: set[str],
    min_valid_price_coverage: float,
    max_initial_missing_days: int,
    keep_signal_tickers: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    kept: list[str] = []
    rows: list[dict[str, object]] = []

    total_rows = len(prices)

    for ticker in prices.columns:
        s = prices[ticker]
        numeric = s.to_numpy(dtype=float, copy=False)
        valid = s.notna().to_numpy() & np.isfinite(numeric) & (numeric > 0)

        valid_count = int(valid.sum())
        valid_coverage = valid_count / total_rows if total_rows else 0.0

        first_valid_pos = int(np.argmax(valid)) if valid_count > 0 else None
        initial_missing_days = (
            total_rows if first_valid_pos is None else first_valid_pos
        )

        is_signal_ticker = str(ticker) in required_signal_tickers

        keep = (
            valid_coverage >= min_valid_price_coverage
            and initial_missing_days <= max_initial_missing_days
        )

        # Signal tickers are protected if they have any usable price history.
        # This prevents random-universe cleaning from silently damaging the actual strategy.
        if keep_signal_tickers and is_signal_ticker and valid_count > 0:
            keep = True

        rows.append(
            {
                "ticker": ticker,
                "valid_count": valid_count,
                "total_rows": total_rows,
                "valid_coverage": valid_coverage,
                "initial_missing_days": initial_missing_days,
                "is_signal_ticker": is_signal_ticker,
                "kept": keep,
            }
        )

        if keep:
            kept.append(ticker)

    report = pd.DataFrame(rows).sort_values(
        ["kept", "valid_coverage", "initial_missing_days"],
        ascending=[True, True, False],
    )

    return prices.loc[:, kept].copy(), report


def prepare_orders(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    signal_horizon: int,
    hold_days: int,
    min_adjusted_confidence: float,
    top_n_per_date: int,
) -> pd.DataFrame:
    frame = signals.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["ticker"] = frame["ticker"].astype(str).map(normalize_ticker)

    frame = frame[
        (frame["horizon"] == signal_horizon)
        & (frame["adjusted_confidence"] >= min_adjusted_confidence)
    ].copy()

    available_tickers = set(map(str, prices.columns))
    frame = frame[frame["ticker"].isin(available_tickers)].copy()

    frame = frame.sort_values(
        ["date", "adjusted_confidence"],
        ascending=[True, False],
    )

    frame = frame.groupby("date", group_keys=False).head(top_n_per_date).copy()

    trading_dates = pd.DatetimeIndex(prices.index)
    date_to_idx = {pd.Timestamp(date): i for i, date in enumerate(trading_dates)}

    entry_dates = []
    exit_dates = []

    for signal_date in frame["date"]:
        idx = date_to_idx.get(pd.Timestamp(signal_date))

        if idx is None:
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            continue

        entry_idx = idx + 1
        exit_idx = idx + 1 + hold_days

        if entry_idx >= len(trading_dates) or exit_idx >= len(trading_dates):
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            continue

        entry_dates.append(pd.Timestamp(trading_dates[entry_idx]))
        exit_dates.append(pd.Timestamp(trading_dates[exit_idx]))

    frame["signal_date"] = frame["date"]
    frame["entry_date"] = entry_dates
    frame["exit_date"] = exit_dates

    frame = frame.dropna(subset=["entry_date", "exit_date"]).copy()

    keep_cols = [
        "signal_date",
        "entry_date",
        "exit_date",
        "ticker",
        "adjusted_confidence",
        "peer_spread_z",
    ]

    frame = frame.loc[:, keep_cols].copy()

    for col in ["signal_date", "entry_date", "exit_date"]:
        frame[col] = pd.to_datetime(frame[col]).dt.strftime("%Y-%m-%d")

    return frame


def summarize_exported_orders(orders: pd.DataFrame) -> dict[str, object]:
    if orders.empty:
        return {
            "order_rows": 0,
            "order_tickers": 0,
            "first_signal_date": None,
            "last_signal_date": None,
        }

    return {
        "order_rows": int(len(orders)),
        "order_tickers": int(orders["ticker"].nunique()),
        "first_signal_date": str(orders["signal_date"].min()),
        "last_signal_date": str(orders["signal_date"].max()),
    }


def main() -> None:
    args = parse_args()

    if args.allow_missing_signal_tickers:
        args.fail_on_missing_signal_tickers = False

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    signals = pd.read_parquet(args.signals)
    signals["ticker"] = signals["ticker"].astype(str).map(normalize_ticker)

    required_signal_tickers = required_signal_tickers_for_download(
        signals,
        signal_horizon=args.signal_horizon,
        min_adjusted_confidence=args.min_adjusted_confidence,
    )

    universe = load_universe(args.universe_file)

    if args.priority_signal_download:
        ordered_universe = sorted(required_signal_tickers) + [
            ticker for ticker in universe if ticker not in required_signal_tickers
        ]
    else:
        ordered_universe = universe.copy()

        for ticker in sorted(required_signal_tickers):
            if ticker not in ordered_universe:
                ordered_universe.append(ticker)

    seen: set[str] = set()
    ordered_universe = [
        ticker
        for ticker in ordered_universe
        if ticker and not (ticker in seen or seen.add(ticker))
    ]

    prices, download_report = download_adjusted_close_chunked(
        ordered_universe,
        start=args.start,
        end=args.end,
        batch_size=args.download_batch_size,
        sleep_seconds=args.download_sleep_seconds,
        retries=args.download_retries,
    )

    prices.columns = [normalize_ticker(c) for c in prices.columns]
    prices = prices.loc[:, ~pd.Index(prices.columns).duplicated()].copy()

    prices = retry_missing_signal_tickers(
        prices,
        required_signal_tickers,
        start=args.start,
        end=args.end,
        sleep_seconds=args.download_sleep_seconds,
        retries=args.download_retries,
    )

    fail_if_missing_signal_tickers(
        prices,
        required_signal_tickers,
        fail_on_missing=args.fail_on_missing_signal_tickers,
        stage="after_download",
    )

    filter_report = None

    if args.drop_bad_price_columns:
        before_cols = len(prices.columns)

        prices, filter_report = filter_price_columns(
            prices,
            required_signal_tickers=required_signal_tickers,
            min_valid_price_coverage=args.min_valid_price_coverage,
            max_initial_missing_days=args.max_initial_missing_days,
            keep_signal_tickers=args.keep_signal_tickers,
        )

        after_cols = len(prices.columns)
        print(
            f"Filtered price columns: kept {after_cols:,} of {before_cols:,} "
            f"tickers using min_valid_price_coverage={args.min_valid_price_coverage:.2f}"
        )

    fail_if_missing_signal_tickers(
        prices,
        required_signal_tickers,
        fail_on_missing=args.fail_on_missing_signal_tickers,
        stage="after_filter",
    )

    orders = prepare_orders(
        signals,
        prices,
        signal_horizon=args.signal_horizon,
        hold_days=args.hold_days,
        min_adjusted_confidence=args.min_adjusted_confidence,
        top_n_per_date=args.top_n_per_date,
    )

    if len(orders) < args.min_exported_orders:
        raise RuntimeError(
            f"Only {len(orders)} orders exported, below --min-exported-orders={args.min_exported_orders}."
        )

    if len(orders) < args.warn_if_exported_orders_below:
        print()
        print(
            f"WARNING: exported only {len(orders)} orders, "
            f"below warning threshold {args.warn_if_exported_orders_below}."
        )
        print(
            "This may be fine for some filters, but verify the strategy was not damaged."
        )

    dtype = np.float32 if args.dtype == "float32" else np.float64
    matrix = prices.to_numpy(dtype=dtype, copy=True)

    prices_bin_path = out_dir / "prices.bin"
    meta_path = out_dir / "prices_meta.json"
    orders_path = out_dir / "orders.csv"
    filter_report_path = out_dir / "price_filter_report.csv"
    download_report_path = out_dir / "download_report.csv"

    matrix.tofile(prices_bin_path)

    order_summary = summarize_exported_orders(orders)

    meta = {
        "format": "row_major_price_matrix",
        "dtype": args.dtype,
        "rows": int(matrix.shape[0]),
        "cols": int(matrix.shape[1]),
        "dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in prices.index],
        "tickers": [str(c) for c in prices.columns],
        "binary_file": prices_bin_path.name,
        "drop_bad_price_columns": bool(args.drop_bad_price_columns),
        "min_valid_price_coverage": float(args.min_valid_price_coverage),
        "max_initial_missing_days": int(args.max_initial_missing_days),
        "required_signal_tickers": sorted(required_signal_tickers),
        "download_batch_size": int(args.download_batch_size),
        "download_retries": int(args.download_retries),
        "download_sleep_seconds": float(args.download_sleep_seconds),
        "order_summary": order_summary,
    }

    meta_path.write_text(json.dumps(meta))

    orders.to_csv(orders_path, index=False)
    download_report.to_csv(download_report_path, index=False)

    if filter_report is not None:
        filter_report.to_csv(filter_report_path, index=False)

    print()
    print("=" * 80)
    print("Export complete")
    print("=" * 80)
    print(f"Saved orders: {orders_path} ({len(orders):,} rows)")
    print(f"Saved prices binary: {prices_bin_path}")
    print(f"Saved prices metadata: {meta_path}")
    print(f"Saved download report: {download_report_path}")

    if filter_report is not None:
        print(f"Saved price filter report: {filter_report_path}")

    print(f"Matrix shape: {matrix.shape[0]:,} rows × {matrix.shape[1]:,} tickers")
    print(f"Matrix dtype: {args.dtype}")
    print(f"Approx binary size: {prices_bin_path.stat().st_size / 1024 / 1024:.2f} MB")

    print()
    print("Order summary:")
    for key, value in order_summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
