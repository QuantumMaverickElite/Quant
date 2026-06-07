# scripts/compare_strategy_vs_buy_hold.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Rust strategy summaries against same-universe buy-and-hold summaries."
    )

    parser.add_argument(
        "--strategy-scorecard",
        default="outputs/reports/rust_stress_scorecard.csv",
    )
    parser.add_argument(
        "--buy-hold-summary",
        required=True,
    )
    parser.add_argument(
        "--out",
        default="outputs/reports/strategy_vs_buy_hold_scorecard.csv",
    )
    parser.add_argument(
        "--markdown-out",
        default="outputs/reports/strategy_vs_buy_hold_scorecard.md",
    )

    return parser.parse_args()


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    exact = {c: c for c in df.columns}
    lowered = {c.lower().strip(): c for c in df.columns}

    for c in candidates:
        if c in exact:
            return exact[c]
        key = c.lower().strip()
        if key in lowered:
            return lowered[key]

    return None


def parse_money(x: object) -> float:
    if pd.isna(x):
        return float("nan")
    s = str(x).replace("$", "").replace(",", "").strip()
    return float(s)


def parse_percent(x: object) -> float:
    if pd.isna(x):
        return float("nan")
    s = str(x).replace("%", "").strip()
    v = float(s)
    return v / 100.0 if abs(v) > 1.0 else v


def parse_multiple(x: object) -> float:
    if pd.isna(x):
        return float("nan")
    s = str(x).replace("x", "").strip()
    return float(s)


def parse_float(x: object) -> float:
    if pd.isna(x):
        return float("nan")
    return float(str(x).replace(",", "").strip())


def get_value(row: pd.Series, col: str | None, default: float = float("nan")) -> float:
    if col is None:
        return default
    return row[col]


def main() -> None:
    args = parse_args()

    strategy = pd.read_csv(args.strategy_scorecard)
    bh = pd.read_csv(args.buy_hold_summary)

    run_col = find_col(strategy, ["Run", "run", "name", "run_name"])
    final_col = find_col(strategy, ["Final Equity", "final_equity"])
    return_col = find_col(strategy, ["Return", "return", "return_multiple", "total_return"])
    dd_col = find_col(strategy, ["Max DD", "max_dd", "max_drawdown"])
    win_col = find_col(strategy, ["Win Rate", "win_rate"])
    sharpe_col = find_col(strategy, ["Sharpe-like", "sharpe_like", "sharpe"])
    same_col = find_col(strategy, ["Same-Date Percentile", "same_date_percentile", "same_date_actual_percentile"])
    random_col = find_col(strategy, ["Random-Date Percentile", "random_date_percentile", "random_dates_actual_percentile"])

    missing = []
    for label, col in [
        ("run", run_col),
        ("final equity", final_col),
        ("return", return_col),
        ("max drawdown", dd_col),
        ("sharpe-like", sharpe_col),
    ]:
        if col is None:
            missing.append(label)

    if missing:
        raise ValueError(
            f"Strategy scorecard missing required fields: {missing}\n"
            f"Available columns: {strategy.columns.tolist()}"
        )

    rows = []

    for _, r in strategy.iterrows():
        raw_return = get_value(r, return_col)

        # Pretty scorecard stores Return as 2.24x.
        # Raw scorecard may store total return as 2.2420, which means final/initial - 1.
        if str(raw_return).strip().endswith("x"):
            return_multiple = parse_multiple(raw_return)
        else:
            rv = parse_float(raw_return)
            return_multiple = rv if rv > 3.0 else 1.0 + rv

        rows.append(
            {
                "system": str(r[run_col]),
                "type": "strategy",
                "final_equity": parse_money(get_value(r, final_col)),
                "return_multiple": return_multiple,
                "max_drawdown": parse_percent(get_value(r, dd_col)),
                "win_rate": parse_percent(get_value(r, win_col)) if win_col else float("nan"),
                "sharpe_like": parse_float(get_value(r, sharpe_col)),
                "same_date_percentile": parse_percent(get_value(r, same_col)) if same_col else float("nan"),
                "random_date_percentile": parse_percent(get_value(r, random_col)) if random_col else float("nan"),
            }
        )

    for _, r in bh.iterrows():
        rows.append(
            {
                "system": str(r["benchmark"]),
                "type": "benchmark",
                "final_equity": float(r["final_equity"]),
                "return_multiple": float(r["return_multiple"]),
                "max_drawdown": float(r["max_drawdown"]),
                "win_rate": float("nan"),
                "sharpe_like": float(r["sharpe_like"]),
                "same_date_percentile": float("nan"),
                "random_date_percentile": float("nan"),
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values("sharpe_like", ascending=False).reset_index(drop=True)

    display = pd.DataFrame(
        {
            "System": out["system"],
            "Type": out["type"],
            "Final Equity": out["final_equity"].map(lambda x: f"${x:,.2f}"),
            "Growth Multiple": out["return_multiple"].map(lambda x: f"{x:.2f}x"),
            "Max DD": out["max_drawdown"].map(lambda x: f"{x:.2%}"),
            "Win Rate": out["win_rate"].map(lambda x: "" if pd.isna(x) else f"{x:.2%}"),
            "Sharpe-like": out["sharpe_like"].map(lambda x: f"{x:.4f}"),
            "Same-Date Percentile": out["same_date_percentile"].map(lambda x: "" if pd.isna(x) else f"{x:.2%}"),
            "Random-Date Percentile": out["random_date_percentile"].map(lambda x: "" if pd.isna(x) else f"{x:.2%}"),
        }
    )

    out_path = Path(args.out)
    md_path = Path(args.markdown_out)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    out.to_csv(out_path, index=False)
    md_path.write_text(display.to_markdown(index=False))

    print(f"Saved combined scorecard -> {out_path}")
    print(f"Saved markdown scorecard -> {md_path}")
    print()
    print(display.to_string(index=False))


if __name__ == "__main__":
    main()
