# scripts/export_returns_matrix.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Rust price matrix into a Rust/GPU-ready returns matrix."
    )

    parser.add_argument(
        "--prices-meta",
        required=True,
        help="Path to prices_meta.json.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for returns.bin and returns_meta.json.",
    )
    parser.add_argument(
        "--return-type",
        choices=["simple", "log"],
        default="log",
    )
    parser.add_argument(
        "--dtype",
        choices=["float32", "float64"],
        default="float32",
    )

    parser.add_argument(
        "--drop-bad-return-columns",
        action="store_true",
        help="Drop tickers with poor return coverage.",
    )
    parser.add_argument(
        "--min-valid-return-coverage",
        type=float,
        default=0.80,
        help="Drop tickers whose return history has fewer finite returns than this fraction.",
    )

    parser.add_argument(
        "--clip-returns",
        action="store_true",
        help="Clip extreme returns after computing returns.",
    )
    parser.add_argument(
        "--max-abs-return",
        type=float,
        default=1.0,
        help="Maximum absolute return allowed when --clip-returns is set.",
    )

    parser.add_argument(
        "--replace-nan-with-zero",
        action="store_true",
        help="Replace NaN returns with 0 after filtering/clipping. Useful for dense matrix operations.",
    )

    return parser.parse_args()


def dtype_from_name(name: str) -> type[np.float32] | type[np.float64]:
    if name == "float32":
        return np.float32
    if name == "float64":
        return np.float64
    raise ValueError(f"Unsupported dtype: {name}")


def load_price_matrix(meta_path: Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(meta_path.read_text())

    dtype = dtype_from_name(meta["dtype"])

    raw = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    expected = int(meta["rows"]) * int(meta["cols"])

    if raw.size != expected:
        raise RuntimeError(
            f"Price binary size mismatch: got {raw.size} values, expected {expected}."
        )

    prices = raw.reshape(int(meta["rows"]), int(meta["cols"]))

    return prices.astype(np.float64, copy=False), meta


def compute_returns(prices: np.ndarray, return_type: str) -> np.ndarray:
    prev = prices[:-1, :]
    curr = prices[1:, :]

    valid = np.isfinite(prev) & np.isfinite(curr) & (prev > 0) & (curr > 0)

    returns = np.full(curr.shape, np.nan, dtype=np.float64)

    if return_type == "simple":
        returns[valid] = curr[valid] / prev[valid] - 1.0
    elif return_type == "log":
        returns[valid] = np.log(curr[valid] / prev[valid])
    else:
        raise ValueError(f"Unsupported return type: {return_type}")

    return returns


def clip_extreme_returns(
    returns: np.ndarray,
    max_abs_return: float,
) -> tuple[np.ndarray, int, int]:
    if max_abs_return <= 0:
        raise ValueError("--max-abs-return must be positive.")

    finite_mask = np.isfinite(returns)
    finite_count = int(finite_mask.sum())

    extreme_mask = finite_mask & (np.abs(returns) > max_abs_return)
    extreme_count = int(extreme_mask.sum())

    clipped = returns.copy()
    clipped[extreme_mask] = np.sign(clipped[extreme_mask]) * max_abs_return

    return clipped, extreme_count, finite_count


def filter_return_columns(
    returns: np.ndarray,
    tickers: list[str],
    min_valid_return_coverage: float,
) -> tuple[np.ndarray, list[str], pd.DataFrame]:
    if not 0 <= min_valid_return_coverage <= 1:
        raise ValueError("--min-valid-return-coverage must be between 0 and 1.")

    valid = np.isfinite(returns)
    coverage = valid.mean(axis=0)

    keep_mask = coverage >= min_valid_return_coverage

    kept_returns = returns[:, keep_mask]
    kept_tickers = [ticker for ticker, keep in zip(tickers, keep_mask) if keep]

    report = pd.DataFrame(
        {
            "ticker": tickers,
            "valid_return_coverage": coverage,
            "kept": keep_mask,
        }
    ).sort_values(
        ["kept", "valid_return_coverage"],
        ascending=[True, True],
    )

    return kept_returns, kept_tickers, report


def summarize_returns(returns: np.ndarray) -> dict[str, float | int]:
    finite = np.isfinite(returns)

    if not finite.any():
        return {
            "finite_count": 0,
            "finite_rate": 0.0,
            "mean_return": float("nan"),
            "std_return": float("nan"),
            "min_return": float("nan"),
            "max_return": float("nan"),
            "max_abs_return": float("nan"),
        }

    vals = returns[finite]

    return {
        "finite_count": int(vals.size),
        "finite_rate": float(finite.mean()),
        "mean_return": float(np.mean(vals)),
        "std_return": float(np.std(vals)),
        "min_return": float(np.min(vals)),
        "max_return": float(np.max(vals)),
        "max_abs_return": float(np.max(np.abs(vals))),
    }


def main() -> None:
    args = parse_args()

    meta_path = Path(args.prices_meta)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prices, price_meta = load_price_matrix(meta_path)

    if prices.shape[0] < 2:
        raise RuntimeError("Price matrix must have at least 2 rows to compute returns.")

    tickers = list(price_meta["tickers"])
    dates = list(price_meta["dates"])[1:]

    if len(tickers) != prices.shape[1]:
        raise RuntimeError(
            f"Ticker count mismatch: metadata has {len(tickers)}, matrix has {prices.shape[1]} cols."
        )

    if len(dates) != prices.shape[0] - 1:
        raise RuntimeError(
            f"Date count mismatch: metadata returns dates has {len(dates)}, expected {prices.shape[0] - 1}."
        )

    returns = compute_returns(prices, args.return_type)

    clipped_count = 0
    finite_before_clip = int(np.isfinite(returns).sum())

    if args.clip_returns:
        returns, clipped_count, finite_before_clip = clip_extreme_returns(
            returns,
            args.max_abs_return,
        )

        print(
            f"Clipped {clipped_count:,} return values above abs threshold "
            f"{args.max_abs_return:.4f} out of {finite_before_clip:,} finite returns."
        )

    filter_report = None

    if args.drop_bad_return_columns:
        before_cols = returns.shape[1]

        returns, tickers, filter_report = filter_return_columns(
            returns,
            tickers,
            args.min_valid_return_coverage,
        )

        after_cols = returns.shape[1]

        print(
            f"Filtered return columns: kept {after_cols:,} of {before_cols:,} "
            f"tickers using min_valid_return_coverage={args.min_valid_return_coverage:.2f}"
        )

    nan_replaced_count = 0

    if args.replace_nan_with_zero:
        nan_mask = ~np.isfinite(returns)
        nan_replaced_count = int(nan_mask.sum())
        returns = returns.copy()
        returns[nan_mask] = 0.0

        print(f"Replaced {nan_replaced_count:,} non-finite returns with 0.0.")

    output_dtype = dtype_from_name(args.dtype)
    matrix = returns.astype(output_dtype, copy=True)

    returns_bin_path = out_dir / "returns.bin"
    returns_meta_path = out_dir / "returns_meta.json"
    filter_report_path = out_dir / "return_filter_report.csv"

    matrix.tofile(returns_bin_path)

    summary = summarize_returns(matrix)

    returns_meta = {
        "format": "row_major_returns_matrix",
        "dtype": args.dtype,
        "rows": int(matrix.shape[0]),
        "cols": int(matrix.shape[1]),
        "dates": dates,
        "tickers": tickers,
        "binary_file": returns_bin_path.name,
        "source_prices_meta": str(meta_path),
        "return_type": args.return_type,
        "drop_bad_return_columns": bool(args.drop_bad_return_columns),
        "min_valid_return_coverage": float(args.min_valid_return_coverage),
        "clip_returns": bool(args.clip_returns),
        "max_abs_return": float(args.max_abs_return),
        "clipped_return_count": int(clipped_count),
        "finite_before_clip": int(finite_before_clip),
        "replace_nan_with_zero": bool(args.replace_nan_with_zero),
        "nan_replaced_count": int(nan_replaced_count),
        "summary": summary,
    }

    returns_meta_path.write_text(json.dumps(returns_meta))

    if filter_report is not None:
        filter_report.to_csv(filter_report_path, index=False)

    print()
    print("=" * 80)
    print("Returns matrix export complete")
    print("=" * 80)
    print(f"Saved returns binary: {returns_bin_path}")
    print(f"Saved returns metadata: {returns_meta_path}")

    if filter_report is not None:
        print(f"Saved return filter report: {filter_report_path}")

    print(f"Matrix shape: {matrix.shape[0]:,} rows × {matrix.shape[1]:,} tickers")
    print(f"Matrix dtype: {args.dtype}")
    print(f"Return type: {args.return_type}")
    print(f"Approx binary size: {returns_bin_path.stat().st_size / 1024 / 1024:.2f} MB")

    print()
    print("Return summary:")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.8f}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
