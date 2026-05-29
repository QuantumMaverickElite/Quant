#!/usr/bin/env python3
"""
Compare Equity Layers
=====================

Compares combined_equity, equity_strategy_equity, options_overlay_equity,
and buy_hold_equity inside each backtest.csv.

Typical usage:

    python scripts/compare_equity_layers.py outputs/regime

Fresh experiment only:

    python scripts/compare_equity_layers.py outputs/regime \
        --run-prefix 20260528 \
        --out outputs/research/extreme_only_layer_comparison.csv \
        --markdown outputs/research/extreme_only_layer_comparison.md
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def safe_float(x: object, default: float = np.nan) -> float:
    try:
        value = float(x)
    except Exception:
        return default
    return value if math.isfinite(value) else default


def pct(x: float) -> float:
    return safe_float(x * 100.0)


def load_backtest(path: Path) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None

    if df.empty or "Date" not in df.columns:
        return None

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")

    return df if not df.empty else None


def annualization_years(index: pd.Index, n_rows: int) -> float:
    if isinstance(index, pd.DatetimeIndex) and len(index) >= 2:
        days = max((index[-1] - index[0]).days, 1)
        return max(days / 365.25, 1 / TRADING_DAYS_PER_YEAR)
    return max(n_rows / TRADING_DAYS_PER_YEAR, 1 / TRADING_DAYS_PER_YEAR)


def clean_equity(df: pd.DataFrame, column: str) -> Optional[pd.Series]:
    if column not in df.columns:
        return None

    s = pd.to_numeric(df[column], errors="coerce")
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    s = s[s > 0]

    if len(s) < 3 or s.nunique() < 3:
        return None

    return s


def compute_max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return safe_float(drawdown.min())


def compute_metrics(df: pd.DataFrame, column: str) -> dict[str, float]:
    equity = clean_equity(df, column)

    if equity is None:
        return {
            "final": np.nan,
            "total_return_pct": np.nan,
            "cagr_pct": np.nan,
            "vol_pct": np.nan,
            "sharpe": np.nan,
            "maxdd_pct": np.nan,
            "calmar": np.nan,
        }

    years = annualization_years(equity.index, len(equity))
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    initial = safe_float(equity.iloc[0])
    final = safe_float(equity.iloc[-1])

    total_return = final / initial - 1.0 if initial > 0 else np.nan
    cagr = (
        (final / initial) ** (1.0 / years) - 1.0
        if initial > 0 and years > 0
        else np.nan
    )

    if len(returns) > 1 and returns.std(ddof=1) > 0:
        vol = safe_float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
        sharpe = safe_float(
            (returns.mean() / returns.std(ddof=1)) * math.sqrt(TRADING_DAYS_PER_YEAR)
        )
    else:
        vol = np.nan
        sharpe = np.nan

    maxdd = compute_max_drawdown(equity)

    if math.isfinite(cagr) and math.isfinite(maxdd) and maxdd < 0:
        calmar = safe_float(cagr / abs(maxdd))
    else:
        calmar = np.nan

    return {
        "final": safe_float(final),
        "total_return_pct": pct(total_return),
        "cagr_pct": pct(cagr),
        "vol_pct": pct(vol),
        "sharpe": safe_float(sharpe),
        "maxdd_pct": pct(maxdd),
        "calmar": safe_float(calmar),
    }


def infer_ticker_and_run(path: Path) -> tuple[str, str]:
    run_id = path.parent.name
    ticker = path.parent.parent.name
    return ticker, run_id


def compare_file(path: Path) -> Optional[dict[str, object]]:
    df = load_backtest(path)
    if df is None:
        return None

    required = {"combined_equity", "equity_strategy_equity"}
    if not required.issubset(set(df.columns)):
        return None

    ticker, run_id = infer_ticker_and_run(path)

    combined = compute_metrics(df, "combined_equity")
    equity = compute_metrics(df, "equity_strategy_equity")
    options = compute_metrics(df, "options_overlay_equity")
    buy_hold = compute_metrics(df, "buy_hold_equity")

    delta_cagr = combined["cagr_pct"] - equity["cagr_pct"]
    delta_sharpe = combined["sharpe"] - equity["sharpe"]
    delta_maxdd = combined["maxdd_pct"] - equity["maxdd_pct"]

    overlay_helped_cagr = delta_cagr > 0
    overlay_helped_sharpe = delta_sharpe > 0
    overlay_helped_drawdown = delta_maxdd > 0

    overlay_help_score = (
        int(overlay_helped_cagr)
        + int(overlay_helped_sharpe)
        + int(overlay_helped_drawdown)
    )

    if overlay_help_score == 3:
        verdict = "HELPED"
    elif overlay_help_score == 2:
        verdict = "MOSTLY_HELPED"
    elif overlay_help_score == 1:
        verdict = "MIXED"
    else:
        verdict = "HURT"

    start_date = (
        str(df.index[0].date()) if isinstance(df.index, pd.DatetimeIndex) else "NA"
    )
    end_date = (
        str(df.index[-1].date()) if isinstance(df.index, pd.DatetimeIndex) else "NA"
    )

    return {
        "ticker": ticker,
        "run_id": run_id,
        "start_date": start_date,
        "end_date": end_date,
        "rows": len(df),
        "verdict": verdict,
        "overlay_help_score": overlay_help_score,
        "combined_cagr_pct": combined["cagr_pct"],
        "equity_cagr_pct": equity["cagr_pct"],
        "delta_cagr_pct": delta_cagr,
        "combined_sharpe": combined["sharpe"],
        "equity_sharpe": equity["sharpe"],
        "delta_sharpe": delta_sharpe,
        "combined_maxdd_pct": combined["maxdd_pct"],
        "equity_maxdd_pct": equity["maxdd_pct"],
        "delta_maxdd_pct": delta_maxdd,
        "options_cagr_pct": options["cagr_pct"],
        "options_sharpe": options["sharpe"],
        "options_maxdd_pct": options["maxdd_pct"],
        "buy_hold_cagr_pct": buy_hold["cagr_pct"],
        "combined_alpha_vs_bh_pct": combined["cagr_pct"] - buy_hold["cagr_pct"],
        "equity_alpha_vs_bh_pct": equity["cagr_pct"] - buy_hold["cagr_pct"],
        "source_csv": str(path),
    }


def discover_backtests(root: Path, run_prefix: Optional[str]) -> list[Path]:
    paths = sorted(root.rglob("backtest.csv"))

    if run_prefix:
        paths = [p for p in paths if p.parent.name.startswith(run_prefix)]

    return paths


def dataframe_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return ""

    safe = df.copy().fillna("")

    def clean(value: object) -> str:
        return str(value).replace("|", r"\|").replace("\n", " ")

    headers = [clean(c) for c in safe.columns]
    rows = [[clean(row[c]) for c in safe.columns] for _, row in safe.iterrows()]

    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in rows]

    return "\n".join([header_line, sep_line, *row_lines])


def write_markdown(
    df: pd.DataFrame, path: Path, root: Path, run_prefix: Optional[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Equity Layer Comparison")
    lines.append("")
    lines.append(f"Root analyzed: `{root}`")
    lines.append(f"Run prefix: `{run_prefix or 'ALL'}`")
    lines.append(f"Runs compared: **{len(df)}**")
    lines.append("")

    if df.empty:
        lines.append("No comparable runs found.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    verdict_counts = df["verdict"].value_counts()
    lines.append("## Verdict Counts")
    lines.append("")
    for verdict, count in verdict_counts.items():
        lines.append(f"- **{verdict}**: {count}")
    lines.append("")

    lines.append("## Top Overlay Improvements")
    lines.append("")
    top_improvements = df.sort_values(
        ["overlay_help_score", "delta_sharpe", "delta_cagr_pct", "delta_maxdd_pct"],
        ascending=[False, False, False, False],
    ).head(20)
    show_cols = [
        "ticker",
        "run_id",
        "verdict",
        "delta_cagr_pct",
        "delta_sharpe",
        "delta_maxdd_pct",
        "combined_cagr_pct",
        "equity_cagr_pct",
        "combined_sharpe",
        "equity_sharpe",
    ]
    lines.append(dataframe_to_markdown_table(top_improvements[show_cols].round(4)))
    lines.append("")

    lines.append("## Worst Overlay Drag")
    lines.append("")
    worst_drag = df.sort_values(
        ["overlay_help_score", "delta_sharpe", "delta_cagr_pct"],
        ascending=[True, True, True],
    ).head(20)
    lines.append(dataframe_to_markdown_table(worst_drag[show_cols].round(4)))
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare combined/equity/options equity layers."
    )
    parser.add_argument(
        "root", type=Path, help="Root folder containing regime backtest outputs."
    )
    parser.add_argument(
        "--run-prefix",
        type=str,
        default=None,
        help="Only include runs whose folder starts with this prefix, e.g. 20260528.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/research/equity_layer_comparison.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("outputs/research/equity_layer_comparison.md"),
        help="Output Markdown report path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Number of rows to print.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()

    if not root.exists():
        raise SystemExit(f"Root path does not exist: {root}")

    rows = []
    for path in discover_backtests(root, args.run_prefix):
        row = compare_file(path)
        if row is not None:
            rows.append(row)

    df = pd.DataFrame(rows)

    if df.empty:
        print("No comparable runs found.")
        print(
            "Need backtest.csv files with combined_equity and equity_strategy_equity."
        )
        return 2

    df = df.sort_values(
        ["overlay_help_score", "delta_sharpe", "delta_cagr_pct", "delta_maxdd_pct"],
        ascending=[False, False, False, False],
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    write_markdown(df, args.markdown, root=root, run_prefix=args.run_prefix)

    display_cols = [
        "ticker",
        "run_id",
        "verdict",
        "delta_cagr_pct",
        "delta_sharpe",
        "delta_maxdd_pct",
        "combined_cagr_pct",
        "equity_cagr_pct",
        "combined_sharpe",
        "equity_sharpe",
    ]

    print("\nEquity Layer Comparison")
    print("=" * 100)
    print(df[display_cols].head(args.limit).round(4).to_string(index=False))
    print("=" * 100)
    print(f"Wrote CSV: {args.out}")
    print(f"Wrote report: {args.markdown}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
