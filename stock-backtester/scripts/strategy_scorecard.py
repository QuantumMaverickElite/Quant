#!/usr/bin/env python3
"""
Strategy Scorecard
==================

Standalone research-evaluation script for the quant backtester project.

Goal
----
Scan a directory of backtest outputs, load equity curves, compute comparable
strategy metrics, rank each run, and write a clean research scorecard.

Typical usage
-------------
From the project root:

    python scripts/strategy_scorecard.py outputs/regime

Optional:

    python scripts/strategy_scorecard.py outputs/regime \
        --out outputs/research/strategy_scorecard.csv \
        --markdown outputs/research/strategy_scorecard.md

This script is intentionally defensive. It searches for likely CSV files and
tries to infer the strategy equity, buy-and-hold equity, date, and exposure
columns from common names.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


# -----------------------------------------------------------------------------
# Column inference
# -----------------------------------------------------------------------------

DATE_CANDIDATES = [
    "date",
    "Date",
    "datetime",
    "Datetime",
    "timestamp",
    "Timestamp",
]

STRATEGY_EQUITY_CANDIDATES = [
    # Preferred modern output columns.
    # combined_equity = equity strategy + options overlay when present.
    "combined_equity",
    "equity_strategy_equity",
    "strategy_equity",
    "equity",
    "portfolio_value",
    "portfolio_equity",
    "account_value",
    "strategy_value",
    "value",
]

BUY_HOLD_EQUITY_CANDIDATES = [
    "buy_hold_equity",
    "buy_and_hold_equity",
    "benchmark_equity",
    "bh_equity",
    "buy_hold",
    "buy_and_hold",
    "benchmark",
]

EXPOSURE_CANDIDATES = [
    "exposure",
    "position",
    "position_size",
    "weight",
    "leverage",
]

RETURNS_CANDIDATES = [
    "combined_strategy_return",
    "equity_strategy_return",
    "strategy_return",
    "returns",
    "return",
    "ret",
]

BUY_HOLD_RETURN_CANDIDATES = [
    "buy_hold_return",
    "buy_and_hold_return",
    "benchmark_return",
    "bh_return",
]

PREFERRED_CSV_NAMES = [
    "equity_curve.csv",
    "equity.csv",
    "results.csv",
    "backtest.csv",
    "backtest_results.csv",
    "portfolio.csv",
    "curve.csv",
]


@dataclass
class ScorecardRow:
    rank: Optional[int]
    score: float
    strategy: str
    ticker: str
    run_id: str
    run_path: str
    rows: int
    start_date: str
    end_date: str
    years: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    annual_vol_pct: float
    sharpe: float
    max_drawdown_pct: float
    calmar: float
    avg_exposure_pct: float
    exposure_efficiency: float
    buy_hold_final_equity: float
    buy_hold_total_return_pct: float
    buy_hold_cagr_pct: float
    alpha_vs_buy_hold_pct: float
    worst_month_pct: float
    best_month_pct: float
    positive_month_pct: float
    worst_year_pct: float
    best_year_pct: float
    source_csv: str
    equity_column: str
    buy_hold_column: str
    exposure_column: str
    notes: str


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def pick_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first matching column from a candidate list."""
    cols = list(df.columns)
    lower_map = {str(c).lower(): c for c in cols}

    for candidate in candidates:
        if candidate in cols:
            return candidate

    for candidate in candidates:
        key = candidate.lower()
        if key in lower_map:
            return lower_map[key]

    return None


def safe_float(value: object, default: float = np.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def infer_strategy_from_path(run_dir: Path, root: Path) -> str:
    """
    Infer strategy name from the root folder.

    Examples:
        outputs/regime/NVDA/run123 -> regime
        outputs/dividend/PG/run123 -> dividend
    """
    try:
        rel = run_dir.relative_to(root)
    except ValueError:
        return root.name or "unknown"

    if root.name not in {"outputs", "output"}:
        return root.name

    parts = rel.parts
    return parts[0] if parts else root.name


def infer_ticker_from_path(run_dir: Path, root: Path) -> str:
    """
    Infer ticker from path.

    Most expected layout:
        outputs/regime/NVDA/<run_id>

    If the user passes outputs/regime directly:
        outputs/regime/NVDA/<run_id>
    """
    try:
        rel = run_dir.relative_to(root)
        parts = rel.parts
    except ValueError:
        parts = run_dir.parts

    # If root is outputs/regime, first part is usually ticker.
    if root.name not in {"outputs", "output"}:
        if len(parts) >= 1:
            return parts[0]
        return run_dir.parent.name

    # If root is outputs, layout is strategy/ticker/run.
    if len(parts) >= 2:
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    return run_dir.parent.name


def annualization_years(index: pd.Index, n_rows: int) -> float:
    """Estimate elapsed years using dates when available; otherwise trading days."""
    if isinstance(index, pd.DatetimeIndex) and len(index) >= 2:
        days = max((index[-1] - index[0]).days, 1)
        return max(days / 365.25, 1 / TRADING_DAYS_PER_YEAR)
    return max(n_rows / TRADING_DAYS_PER_YEAR, 1 / TRADING_DAYS_PER_YEAR)


def clean_numeric_series(s: pd.Series) -> pd.Series:
    out = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return out.dropna()


def compute_drawdown(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return equity / running_max - 1.0


def compute_monthly_returns(equity: pd.Series) -> pd.Series:
    if not isinstance(equity.index, pd.DatetimeIndex):
        return pd.Series(dtype=float)
    monthly = equity.resample("ME").last().pct_change().dropna()
    return monthly.replace([np.inf, -np.inf], np.nan).dropna()


def compute_yearly_returns(equity: pd.Series) -> pd.Series:
    if not isinstance(equity.index, pd.DatetimeIndex):
        return pd.Series(dtype=float)
    yearly = equity.resample("YE").last().pct_change().dropna()
    return yearly.replace([np.inf, -np.inf], np.nan).dropna()


def pct(x: float) -> float:
    return safe_float(x * 100.0)


def finite_or_nan(x: float) -> float:
    return safe_float(x, np.nan)


# -----------------------------------------------------------------------------
# Discovery and loading
# -----------------------------------------------------------------------------


def discover_candidate_csvs(root: Path) -> list[Path]:
    """Find likely backtest CSVs under root."""
    if root.is_file() and root.suffix.lower() == ".csv":
        return [root]

    all_csvs = list(root.rglob("*.csv"))
    if not all_csvs:
        return []

    def score_path(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        score = 0
        if name in PREFERRED_CSV_NAMES:
            score += 100
        if "equity" in name:
            score += 50
        if "result" in name:
            score += 25
        if "summary" in name:
            score -= 25
        if "trade" in name:
            score -= 20
        return (-score, str(path))

    return sorted(all_csvs, key=score_path)


def group_csvs_by_run(csvs: Iterable[Path], root: Path) -> dict[Path, list[Path]]:
    """
    Group CSVs by run directory.

    In the simplest case, each run directory contains one equity CSV.
    """
    grouped: dict[Path, list[Path]] = {}
    for csv in csvs:
        run_dir = csv.parent
        grouped.setdefault(run_dir, []).append(csv)

    for run_dir in grouped:
        grouped[run_dir] = sorted(
            grouped[run_dir],
            key=lambda p: (
                0 if p.name.lower() in PREFERRED_CSV_NAMES else 1,
                0 if "equity" in p.name.lower() else 1,
                str(p),
            ),
        )
    return grouped


def try_load_equity_csv(
    path: Path,
) -> Optional[tuple[pd.DataFrame, dict[str, Optional[str]], str]]:
    """
    Try loading a CSV and infer useful columns.

    Returns:
        (df, column_map, notes) or None if the CSV does not look useful.
    """
    try:
        df = pd.read_csv(path)
    except Exception:
        return None

    if df.empty or len(df) < 3:
        return None

    date_col = pick_column(df, DATE_CANDIDATES)
    strategy_col = pick_column(df, STRATEGY_EQUITY_CANDIDATES)
    buy_hold_col = pick_column(df, BUY_HOLD_EQUITY_CANDIDATES)
    exposure_col = pick_column(df, EXPOSURE_CANDIDATES)
    returns_col = pick_column(df, RETURNS_CANDIDATES)
    buy_hold_returns_col = pick_column(df, BUY_HOLD_RETURN_CANDIDATES)

    notes = []

    if date_col is not None:
        parsed_dates = pd.to_datetime(df[date_col], errors="coerce")
        if parsed_dates.notna().sum() >= max(3, int(0.5 * len(df))):
            df = df.copy()
            df[date_col] = parsed_dates
            df = df.dropna(subset=[date_col]).sort_values(date_col)
            df = df.set_index(date_col)
        else:
            notes.append(f"date column {date_col!r} could not be parsed")

    if strategy_col is None:
        # Last-resort fallback: use a returns column to construct equity.
        if returns_col is not None:
            returns = clean_numeric_series(df[returns_col])
            if len(returns) >= 3:
                df = df.copy()
                df["_constructed_strategy_equity"] = (1.0 + returns).cumprod()
                strategy_col = "_constructed_strategy_equity"
                notes.append(
                    f"constructed strategy equity from returns column {returns_col!r}"
                )
        else:
            return None

    if strategy_col is None:
        return None

    strategy_series = clean_numeric_series(df[strategy_col])
    if len(strategy_series) < 3:
        return None

    # Reject files that are likely not equity curves.
    if strategy_series.nunique() < 3:
        return None

    column_map = {
        "date": date_col,
        "strategy_equity": strategy_col,
        "buy_hold_equity": buy_hold_col,
        "exposure": exposure_col,
        "returns": returns_col,
        "buy_hold_returns": buy_hold_returns_col,
    }

    return df, column_map, "; ".join(notes)


def load_best_equity_for_run(
    run_dir: Path, csvs: list[Path]
) -> Optional[tuple[pd.DataFrame, dict[str, Optional[str]], Path, str]]:
    """Pick the first CSV in a run directory that looks like an equity curve."""
    for csv_path in csvs:
        loaded = try_load_equity_csv(csv_path)
        if loaded is not None:
            df, column_map, notes = loaded
            return df, column_map, csv_path, notes
    return None


# -----------------------------------------------------------------------------
# Metric calculation
# -----------------------------------------------------------------------------


def compute_metrics_for_run(
    run_dir: Path,
    root: Path,
    df: pd.DataFrame,
    column_map: dict[str, Optional[str]],
    source_csv: Path,
    notes: str,
) -> ScorecardRow:
    strategy_col = column_map["strategy_equity"]
    buy_hold_col = column_map["buy_hold_equity"]
    exposure_col = column_map["exposure"]

    assert strategy_col is not None

    equity = clean_numeric_series(df[strategy_col]).astype(float)
    equity = equity[equity > 0]

    # Preserve datetime index when possible after cleaning.
    if isinstance(df.index, pd.DatetimeIndex):
        equity = pd.to_numeric(df[strategy_col], errors="coerce")
        equity = equity.replace([np.inf, -np.inf], np.nan).dropna()
        equity = equity[equity > 0]

    if len(equity) < 3:
        raise ValueError(f"Not enough equity data in {source_csv}")

    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    years = annualization_years(equity.index, len(equity))

    initial_equity = safe_float(equity.iloc[0])
    final_equity = safe_float(equity.iloc[-1])
    total_return = final_equity / initial_equity - 1.0 if initial_equity > 0 else np.nan
    cagr = (
        (final_equity / initial_equity) ** (1.0 / years) - 1.0
        if initial_equity > 0 and years > 0
        else np.nan
    )

    annual_vol = (
        safe_float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
        if len(returns) > 1
        else np.nan
    )
    sharpe = (
        safe_float(
            (returns.mean() / returns.std(ddof=1)) * math.sqrt(TRADING_DAYS_PER_YEAR)
        )
        if len(returns) > 1 and returns.std(ddof=1) > 0
        else np.nan
    )

    drawdown = compute_drawdown(equity)
    max_drawdown = safe_float(drawdown.min())
    calmar = safe_float(cagr / abs(max_drawdown)) if max_drawdown < 0 else np.nan

    monthly_returns = compute_monthly_returns(equity)
    yearly_returns = compute_yearly_returns(equity)

    worst_month = (
        safe_float(monthly_returns.min(), np.nan)
        if not monthly_returns.empty
        else np.nan
    )
    best_month = (
        safe_float(monthly_returns.max(), np.nan)
        if not monthly_returns.empty
        else np.nan
    )
    positive_month = (
        safe_float((monthly_returns > 0).mean(), np.nan)
        if not monthly_returns.empty
        else np.nan
    )
    worst_year = (
        safe_float(yearly_returns.min(), np.nan) if not yearly_returns.empty else np.nan
    )
    best_year = (
        safe_float(yearly_returns.max(), np.nan) if not yearly_returns.empty else np.nan
    )

    if exposure_col is not None and exposure_col in df.columns:
        exposure = (
            pd.to_numeric(df[exposure_col], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        avg_exposure = (
            safe_float(exposure.abs().mean(), np.nan) if len(exposure) else np.nan
        )
    else:
        avg_exposure = np.nan

    if math.isfinite(avg_exposure) and avg_exposure > 0:
        # If exposure looks like 0..100, normalize it to 0..1.
        avg_exposure_normalized = (
            avg_exposure / 100.0 if avg_exposure > 5 else avg_exposure
        )
        exposure_efficiency = (
            safe_float(cagr / avg_exposure_normalized)
            if avg_exposure_normalized > 0
            else np.nan
        )
    else:
        avg_exposure_normalized = np.nan
        exposure_efficiency = np.nan

    buy_hold_final = np.nan
    buy_hold_total_return = np.nan
    buy_hold_cagr = np.nan
    alpha_vs_buy_hold = np.nan

    if buy_hold_col is not None and buy_hold_col in df.columns:
        bh = clean_numeric_series(df[buy_hold_col]).astype(float)
        bh = bh[bh > 0]
        if len(bh) >= 3:
            bh_initial = safe_float(bh.iloc[0])
            buy_hold_final = safe_float(bh.iloc[-1])
            buy_hold_total_return = (
                buy_hold_final / bh_initial - 1.0 if bh_initial > 0 else np.nan
            )
            buy_hold_cagr = (
                (buy_hold_final / bh_initial) ** (1.0 / years) - 1.0
                if bh_initial > 0 and years > 0
                else np.nan
            )
            alpha_vs_buy_hold = (
                cagr - buy_hold_cagr
                if math.isfinite(cagr) and math.isfinite(buy_hold_cagr)
                else np.nan
            )

    start_date = (
        str(equity.index[0].date())
        if isinstance(equity.index, pd.DatetimeIndex)
        else "NA"
    )
    end_date = (
        str(equity.index[-1].date())
        if isinstance(equity.index, pd.DatetimeIndex)
        else "NA"
    )

    return ScorecardRow(
        rank=None,
        score=np.nan,
        strategy=infer_strategy_from_path(run_dir, root),
        ticker=infer_ticker_from_path(run_dir, root),
        run_id=run_dir.name,
        run_path=str(run_dir),
        rows=int(len(equity)),
        start_date=start_date,
        end_date=end_date,
        years=finite_or_nan(years),
        final_equity=finite_or_nan(final_equity),
        total_return_pct=pct(total_return),
        cagr_pct=pct(cagr),
        annual_vol_pct=pct(annual_vol),
        sharpe=finite_or_nan(sharpe),
        max_drawdown_pct=pct(max_drawdown),
        calmar=finite_or_nan(calmar),
        avg_exposure_pct=pct(avg_exposure_normalized),
        exposure_efficiency=finite_or_nan(exposure_efficiency),
        buy_hold_final_equity=finite_or_nan(buy_hold_final),
        buy_hold_total_return_pct=pct(buy_hold_total_return),
        buy_hold_cagr_pct=pct(buy_hold_cagr),
        alpha_vs_buy_hold_pct=pct(alpha_vs_buy_hold),
        worst_month_pct=pct(worst_month),
        best_month_pct=pct(best_month),
        positive_month_pct=pct(positive_month),
        worst_year_pct=pct(worst_year),
        best_year_pct=pct(best_year),
        source_csv=str(source_csv),
        equity_column=strategy_col or "",
        buy_hold_column=buy_hold_col or "",
        exposure_column=exposure_col or "",
        notes=notes,
    )


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------


def percentile_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Return 0..1 percentile ranks. Missing values get neutral 0.5."""
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() <= 1:
        return pd.Series(0.5, index=series.index)

    ranks = s.rank(pct=True, ascending=not higher_is_better)
    return ranks.fillna(0.5)


def add_scores(df: pd.DataFrame, mode: str = "balanced") -> pd.DataFrame:
    """Add composite score and rank columns."""
    if df.empty:
        return df

    out = df.copy()

    components = {
        "sharpe": percentile_rank(out["sharpe"], higher_is_better=True),
        "cagr": percentile_rank(out["cagr_pct"], higher_is_better=True),
        "drawdown": percentile_rank(
            out["max_drawdown_pct"], higher_is_better=True
        ),  # less negative is better
        "alpha": percentile_rank(out["alpha_vs_buy_hold_pct"], higher_is_better=True),
        "calmar": percentile_rank(out["calmar"], higher_is_better=True),
        "exposure_efficiency": percentile_rank(
            out["exposure_efficiency"], higher_is_better=True
        ),
    }

    if mode == "aggressive":
        weights = {
            "cagr": 0.35,
            "alpha": 0.25,
            "sharpe": 0.20,
            "calmar": 0.10,
            "drawdown": 0.05,
            "exposure_efficiency": 0.05,
        }
    elif mode == "defensive":
        weights = {
            "drawdown": 0.30,
            "sharpe": 0.25,
            "calmar": 0.20,
            "cagr": 0.10,
            "alpha": 0.10,
            "exposure_efficiency": 0.05,
        }
    elif mode == "alpha":
        weights = {
            "alpha": 0.40,
            "sharpe": 0.20,
            "cagr": 0.15,
            "calmar": 0.15,
            "drawdown": 0.05,
            "exposure_efficiency": 0.05,
        }
    else:
        weights = {
            "sharpe": 0.30,
            "cagr": 0.20,
            "drawdown": 0.20,
            "alpha": 0.15,
            "calmar": 0.10,
            "exposure_efficiency": 0.05,
        }

    score = pd.Series(0.0, index=out.index)
    for name, weight in weights.items():
        score += components[name] * weight

    out["score"] = (score * 100).round(2)
    out = out.sort_values(
        ["score", "sharpe", "cagr_pct"], ascending=[False, False, False]
    )
    out["rank"] = range(1, len(out) + 1)

    preferred_cols = [
        "rank",
        "score",
        "strategy",
        "ticker",
        "run_id",
        "start_date",
        "end_date",
        "years",
        "final_equity",
        "total_return_pct",
        "cagr_pct",
        "annual_vol_pct",
        "sharpe",
        "max_drawdown_pct",
        "calmar",
        "avg_exposure_pct",
        "exposure_efficiency",
        "buy_hold_total_return_pct",
        "buy_hold_cagr_pct",
        "alpha_vs_buy_hold_pct",
        "worst_month_pct",
        "best_month_pct",
        "positive_month_pct",
        "worst_year_pct",
        "best_year_pct",
        "rows",
        "run_path",
        "source_csv",
        "equity_column",
        "buy_hold_column",
        "exposure_column",
        "notes",
    ]

    existing_cols = [c for c in preferred_cols if c in out.columns]
    other_cols = [c for c in out.columns if c not in existing_cols]
    return out[existing_cols + other_cols]


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------


def build_scorecard(root: Path, mode: str = "balanced") -> pd.DataFrame:
    csvs = discover_candidate_csvs(root)
    if not csvs:
        return pd.DataFrame()

    grouped = group_csvs_by_run(csvs, root)
    rows: list[dict] = []
    errors: list[str] = []

    for run_dir, run_csvs in grouped.items():
        loaded = load_best_equity_for_run(run_dir, run_csvs)
        if loaded is None:
            continue

        df, column_map, source_csv, notes = loaded
        try:
            row = compute_metrics_for_run(
                run_dir, root, df, column_map, source_csv, notes
            )
            rows.append(asdict(row))
        except Exception as exc:
            errors.append(f"{run_dir}: {exc}")

    scorecard = pd.DataFrame(rows)
    if scorecard.empty:
        return scorecard

    scorecard = add_scores(scorecard, mode=mode)

    if errors:
        # Attach errors as metadata-ish comments in stdout later rather than CSV rows.
        scorecard.attrs["errors"] = errors

    return scorecard


def format_terminal_table(df: pd.DataFrame, limit: int = 20) -> str:
    if df.empty:
        return "No scorecard rows found."

    display_cols = [
        "rank",
        "score",
        "strategy",
        "ticker",
        "run_id",
        "cagr_pct",
        "sharpe",
        "max_drawdown_pct",
        "alpha_vs_buy_hold_pct",
        "avg_exposure_pct",
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    shown = df.head(limit)[display_cols].copy()

    for col in [
        "score",
        "cagr_pct",
        "sharpe",
        "max_drawdown_pct",
        "alpha_vs_buy_hold_pct",
        "avg_exposure_pct",
    ]:
        if col in shown.columns:
            shown[col] = pd.to_numeric(shown[col], errors="coerce").round(2)

    return shown.to_string(index=False)


def dataframe_to_markdown_table(df: pd.DataFrame) -> str:
    """Render a small DataFrame as a markdown table without requiring tabulate."""
    if df.empty:
        return ""

    safe = df.copy().fillna("")

    def clean_cell(value: object) -> str:
        text = str(value)
        text = text.replace("|", r"\|")
        text = text.replace(" ", " ")
        return text

    headers = [clean_cell(c) for c in safe.columns]
    rows = []
    for _, row in safe.iterrows():
        rows.append([clean_cell(row[c]) for c in safe.columns])

    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in rows]

    return " ".join([header_line, separator_line, *row_lines])


def write_markdown_report(df: pd.DataFrame, path: Path, root: Path, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Strategy Scorecard")
    lines.append("")
    lines.append(f"Root analyzed: `{root}`")
    lines.append(f"Ranking mode: `{mode}`")
    lines.append(f"Runs scored: **{len(df)}**")
    lines.append("")

    if df.empty:
        lines.append("No valid backtest equity curves were found.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    top = df.iloc[0]
    lines.append("## Best Overall Run")
    lines.append("")
    lines.append(
        f"**#{int(top['rank'])}: {top['strategy']} / {top['ticker']} / {top['run_id']}** "
        f"with score **{top['score']:.2f}**."
    )
    lines.append("")
    lines.append(
        f"CAGR: **{top['cagr_pct']:.2f}%**, Sharpe: **{top['sharpe']:.2f}**, "
        f"MaxDD: **{top['max_drawdown_pct']:.2f}%**, "
        f"Alpha vs B&H: **{top['alpha_vs_buy_hold_pct']:.2f}%**."
    )
    lines.append("")

    def add_leader(section: str, col: str, higher_is_better: bool = True) -> None:
        valid = df[pd.to_numeric(df[col], errors="coerce").notna()].copy()
        if valid.empty:
            return
        valid[col] = pd.to_numeric(valid[col], errors="coerce")
        leader = valid.sort_values(col, ascending=not higher_is_better).iloc[0]
        lines.append(f"## {section}")
        lines.append("")
        lines.append(
            f"**{leader['strategy']} / {leader['ticker']} / {leader['run_id']}**: "
            f"{leader[col]:.2f}"
        )
        lines.append("")

    add_leader("Highest CAGR", "cagr_pct", True)
    add_leader("Best Sharpe", "sharpe", True)
    add_leader("Smallest Max Drawdown", "max_drawdown_pct", True)
    add_leader("Best Alpha vs Buy-and-Hold", "alpha_vs_buy_hold_pct", True)

    lines.append("## Top Runs")
    lines.append("")

    table_cols = [
        "rank",
        "score",
        "strategy",
        "ticker",
        "run_id",
        "cagr_pct",
        "sharpe",
        "max_drawdown_pct",
        "alpha_vs_buy_hold_pct",
    ]
    table_cols = [c for c in table_cols if c in df.columns]
    top_table = df.head(20)[table_cols].copy()
    lines.append(dataframe_to_markdown_table(top_table))
    lines.append("")

    errors = df.attrs.get("errors", [])
    if errors:
        lines.append("## Skipped / Error Notes")
        lines.append("")
        for error in errors[:25]:
            lines.append(f"- {error}")
        if len(errors) > 25:
            lines.append(f"- ...and {len(errors) - 25} more.")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a strategy scorecard from backtest output folders."
    )
    parser.add_argument(
        "root",
        type=Path,
        help="Root output folder or a single CSV file. Example: outputs/regime",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/research/strategy_scorecard.csv"),
        help="Path to write the CSV scorecard.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("outputs/research/strategy_scorecard.md"),
        help="Path to write the markdown report.",
    )
    parser.add_argument(
        "--mode",
        choices=["balanced", "aggressive", "defensive", "alpha"],
        default="balanced",
        help="Composite scoring mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of top rows to print in the terminal.",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Do not write a markdown report.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    root = args.root.expanduser().resolve()

    if not root.exists():
        print(f"ERROR: root path does not exist: {root}", file=sys.stderr)
        return 1

    scorecard = build_scorecard(root, mode=args.mode)

    if scorecard.empty:
        print("No valid backtest equity curves found.")
        print(
            "Checked for CSV files with columns like equity, strategy_equity, portfolio_value, date, buy_hold_equity."
        )
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    scorecard.to_csv(args.out, index=False)

    if not args.no_markdown:
        write_markdown_report(scorecard, args.markdown, root=root, mode=args.mode)

    print("\nStrategy Scorecard")
    print("=" * 80)
    print(format_terminal_table(scorecard, limit=args.limit))
    print("=" * 80)
    print(f"Wrote CSV: {args.out}")
    if not args.no_markdown:
        print(f"Wrote report: {args.markdown}")

    errors = scorecard.attrs.get("errors", [])
    if errors:
        print(f"Skipped/error runs: {len(errors)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
