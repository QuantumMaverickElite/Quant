from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def latest_runs_for_ticker(base_dir: Path, ticker: str, n: int = 3) -> list[Path]:
    ticker_dir = base_dir / ticker

    if not ticker_dir.exists():
        return []

    run_dirs = sorted(
        [p for p in ticker_dir.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    csvs = []
    for run_dir in run_dirs:
        csv_path = run_dir / "backtest.csv"
        if csv_path.exists():
            csvs.append(csv_path)
        if len(csvs) >= n:
            break

    return list(reversed(csvs))


def infer_mode(df: pd.DataFrame) -> str:
    has_router = "route_risk_multiplier" in df.columns
    has_options = (
        "options_overlay_return" in df.columns
        and df["options_overlay_return"].abs().sum() > 0
    )

    if has_router and has_options:
        return "router_options"
    if has_router:
        return "router"
    return "baseline"


def load_returns(path: Path) -> tuple[str, pd.Series]:
    df = pd.read_csv(path, index_col=0, parse_dates=True)

    mode = infer_mode(df)

    if "combined_strategy_return" in df.columns:
        returns = df["combined_strategy_return"].fillna(0.0)
    elif "strategy_return" in df.columns:
        returns = df["strategy_return"].fillna(0.0)
    else:
        raise ValueError(f"No strategy return column found in {path}")

    returns.name = mode
    return mode, returns


def annual_stats(returns: pd.Series) -> pd.DataFrame:
    rows = []

    for year, r in returns.groupby(returns.index.year):
        r = r.fillna(0.0)

        total_return = float((1.0 + r).prod() - 1.0)
        vol_ann = float(r.std() * (252**0.5))

        sharpe = 0.0
        if r.std() > 0:
            sharpe = float((r.mean() / r.std()) * (252**0.5))

        equity = (1.0 + r).cumprod()
        drawdown = equity / equity.cummax() - 1.0

        rows.append(
            {
                "year": int(year),
                "return": total_return,
                "vol_ann": vol_ann,
                "sharpe": sharpe,
                "max_drawdown": float(drawdown.min()),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare latest regime backtest runs by calendar year."
    )
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--base-dir", default="outputs/regime")
    parser.add_argument("--runs-per-ticker", type=int, default=3)

    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    ticker = args.ticker.upper()

    csv_paths = latest_runs_for_ticker(
        base_dir=base_dir,
        ticker=ticker,
        n=args.runs_per_ticker,
    )

    if len(csv_paths) < 2:
        raise SystemExit(f"Not enough runs found for {ticker}.")

    frames = []

    for path in csv_paths:
        mode, returns = load_returns(path)
        stats = annual_stats(returns)
        stats.insert(0, "mode", mode)
        stats.insert(0, "ticker", ticker)
        stats["csv_path"] = str(path)
        frames.append(stats)

    out = pd.concat(frames, ignore_index=True)

    out = out.sort_values(["year", "mode"]).reset_index(drop=True)

    out_dir = Path("outputs/comparisons/by_year") / ticker
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "yearly_comparison.csv"
    out.to_csv(out_path, index=False)

    display_cols = [
        "ticker",
        "year",
        "mode",
        "return",
        "vol_ann",
        "sharpe",
        "max_drawdown",
    ]

    print(
        out[display_cols].to_string(
            index=False,
            float_format=lambda x: f"{x:0.4f}",
        )
    )
    print(f"\nSaved yearly comparison -> {out_path}")


if __name__ == "__main__":
    main()
