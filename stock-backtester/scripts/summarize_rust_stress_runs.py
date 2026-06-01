# scripts/summarize_rust_stress_runs.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Rust stress-test output directories into a clean scorecard."
    )
    parser.add_argument(
        "--run-dirs",
        nargs="+",
        required=True,
        help="Rust stress output directories.",
    )
    parser.add_argument(
        "--out",
        default="outputs/reports/rust_stress_scorecard.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--markdown-out",
        default=None,
        help="Optional Markdown output path. Defaults to CSV path with .md suffix.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def clean_run_name(run_dir: Path) -> str:
    name = run_dir.name
    name = name.removesuffix("_20k")
    name = name.replace("peer_spread_", "")
    name = name.replace("_v1", "")
    return name


def first_value(df: pd.DataFrame, candidates: list[str], default=None):
    if df.empty:
        return default
    for col in candidates:
        if col in df.columns:
            return df[col].iloc[0]
    return default


def mc_value(mc: pd.DataFrame, control_name: str, candidates: list[str], default=None):
    if mc.empty:
        return default

    control_col = None
    for possible in ["control_test", "control", "control_name", "test"]:
        if possible in mc.columns:
            control_col = possible
            break

    if control_col is None:
        return default

    rows = mc[mc[control_col].astype(str) == control_name]
    if rows.empty:
        return default

    return first_value(rows, candidates, default=default)


def pct(x) -> str:
    if pd.isna(x):
        return ""
    try:
        return f"{100.0 * float(x):.2f}%"
    except Exception:
        return ""


def xret(x) -> str:
    if pd.isna(x):
        return ""
    try:
        return f"{float(x):.2f}x"
    except Exception:
        return ""


def money(x) -> str:
    if pd.isna(x):
        return ""
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return ""


def num(x) -> str:
    if pd.isna(x):
        return ""
    try:
        return f"{int(x):,}"
    except Exception:
        return ""


def summarize_run(run_dir: Path) -> dict[str, object]:
    actual = read_csv(run_dir / "actual_summary.csv")
    mc = read_csv(run_dir / "monte_carlo_summary.csv")
    equity = read_csv(run_dir / "actual_equity.csv")
    trades = read_csv(run_dir / "actual_closed_trades.csv")

    row: dict[str, object] = {
        "run": clean_run_name(run_dir),
        "run_dir": str(run_dir),
    }

    row["orders"] = len(trades) if not trades.empty else None
    row["tickers"] = trades["ticker"].nunique() if "ticker" in trades.columns else None

    if "signal_date" in trades.columns:
        row["first_signal_date"] = trades["signal_date"].min()
        row["last_signal_date"] = trades["signal_date"].max()
    elif "entry_date" in trades.columns:
        row["first_signal_date"] = trades["entry_date"].min()
        row["last_signal_date"] = trades["entry_date"].max()

    row["final_equity"] = first_value(actual, ["final_equity", "actual_final_equity"])
    row["total_return"] = first_value(actual, ["total_return", "actual_total_return"])
    row["max_drawdown"] = first_value(actual, ["max_drawdown", "actual_max_drawdown"])
    row["win_rate"] = first_value(actual, ["win_rate", "actual_win_rate"])
    row["sharpe_like"] = first_value(actual, ["sharpe_like", "actual_sharpe_like"])

    if row["final_equity"] is None and not equity.empty:
        for col in ["equity", "portfolio_value", "final_equity"]:
            if col in equity.columns:
                row["final_equity"] = equity[col].iloc[-1]
                break

    controls = [
        ("random_dates_random_tickers", "random_dates"),
        ("same_dates_random_tickers", "same_dates"),
    ]

    for control, short in controls:
        row[f"{short}_actual_percentile"] = mc_value(
            mc,
            control,
            ["actual_percentile", "control_actual_percentile"],
        )
        row[f"{short}_prob_random_beats_actual"] = mc_value(
            mc,
            control,
            ["prob_random_beats_actual", "control_prob_random_beats_actual"],
        )
        row[f"{short}_mc_median_return"] = mc_value(
            mc,
            control,
            ["mc_median", "mc_median_total_return", "control_mc_median_total_return"],
        )
        row[f"{short}_mc_p95_return"] = mc_value(
            mc,
            control,
            ["mc_p95", "mc_p95_total_return", "control_mc_p95_total_return"],
        )

    return row


def build_display(scorecard: pd.DataFrame) -> pd.DataFrame:
    display = pd.DataFrame()

    display["Run"] = scorecard["run"]
    display["Closed Trades"] = scorecard["orders"].map(num)
    display["Closed Trade Tickers"] = scorecard["tickers"].map(num)
    display["Final Equity"] = scorecard["final_equity"].map(money)
    display["Return"] = scorecard["total_return"].map(xret)
    display["Max DD"] = scorecard["max_drawdown"].map(pct)
    display["Win Rate"] = scorecard["win_rate"].map(pct)
    display["Sharpe-like"] = scorecard["sharpe_like"].map(
        lambda x: "" if pd.isna(x) else f"{float(x):.4f}"
    )

    display["Same-Date Percentile"] = scorecard["same_dates_actual_percentile"].map(pct)
    display["Same-Date Beats"] = scorecard["same_dates_prob_random_beats_actual"].map(pct)
    display["Same-Date MC Median"] = scorecard["same_dates_mc_median_return"].map(xret)
    display["Same-Date MC P95"] = scorecard["same_dates_mc_p95_return"].map(xret)

    display["Random-Date Percentile"] = scorecard["random_dates_actual_percentile"].map(pct)
    display["Random-Date Beats"] = scorecard["random_dates_prob_random_beats_actual"].map(pct)
    display["Random-Date MC Median"] = scorecard["random_dates_mc_median_return"].map(xret)
    display["Random-Date MC P95"] = scorecard["random_dates_mc_p95_return"].map(xret)

    return display


def main() -> None:
    args = parse_args()

    rows = []
    for raw in args.run_dirs:
        run_dir = Path(raw)
        if not run_dir.exists():
            print(f"Skipping missing run dir: {run_dir}")
            continue
        rows.append(summarize_run(run_dir))

    if not rows:
        raise RuntimeError("No valid run directories found.")

    scorecard = pd.DataFrame(rows)

    def sort_key(name: str) -> int:
        for n in [5, 10, 20, 50, 100]:
            if f"top{n}" in name:
                return n
        return 999

    scorecard["_sort"] = scorecard["run"].map(sort_key)
    scorecard = scorecard.sort_values(["_sort", "run"]).drop(columns=["_sort"]).reset_index(drop=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    scorecard.to_csv(out, index=False)

    markdown_out = Path(args.markdown_out) if args.markdown_out else out.with_suffix(".md")
    display = build_display(scorecard)
    markdown_out.write_text(display.to_markdown(index=False) + "\n")

    print(f"Saved raw scorecard: {out}")
    print(f"Saved pretty scorecard: {markdown_out}")
    print()
    print(display.to_string(index=False))


if __name__ == "__main__":
    main()
