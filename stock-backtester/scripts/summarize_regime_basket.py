from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def compute_summary_from_csv(path: Path) -> dict:
    df = pd.read_csv(path, index_col=0, parse_dates=True)

    if "combined_strategy_return" in df.columns:
        returns = df["combined_strategy_return"].fillna(0.0)
    elif "strategy_return" in df.columns:
        returns = df["strategy_return"].fillna(0.0)
    else:
        raise ValueError(f"No return column found in {path}")

    if "combined_equity" in df.columns:
        equity = df["combined_equity"].ffill()
    elif "equity" in df.columns:
        equity = df["equity"].ffill()
    else:
        equity = (1.0 + returns).cumprod()

    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    final_equity = float(equity.iloc[-1])
    cagr = final_equity ** (1.0 / years) - 1.0

    vol = float(returns.std() * (252**0.5))
    sharpe = (
        float((returns.mean() / returns.std()) * (252**0.5))
        if returns.std() > 0
        else 0.0
    )

    drawdown = equity / equity.cummax() - 1.0

    return {
        "final_equity": final_equity,
        "cagr": cagr,
        "vol_ann": vol,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "csv_path": str(path),
    }


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize latest regime basket backtest runs."
    )
    parser.add_argument("--tickers", nargs="+", default=["SPY", "QQQ", "AAPL"])
    parser.add_argument("--base-dir", default="outputs/regime")
    parser.add_argument("--runs-per-ticker", type=int, default=3)

    args = parser.parse_args()

    base_dir = Path(args.base_dir)

    rows = []

    for ticker in args.tickers:
        csv_paths = latest_runs_for_ticker(base_dir, ticker, n=args.runs_per_ticker)

        for path in csv_paths:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            mode = infer_mode(df)
            stats = compute_summary_from_csv(path)

            rows.append(
                {
                    "ticker": ticker,
                    "mode": mode,
                    **stats,
                }
            )

    out = pd.DataFrame(rows)

    if out.empty:
        raise SystemExit("No runs found.")

    out = out.sort_values(["ticker", "mode"]).reset_index(drop=True)

    out_dir = Path("outputs/comparisons/basket")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "basket_summary.csv"
    out.to_csv(out_path, index=False)

    display_cols = [
        "ticker",
        "mode",
        "final_equity",
        "cagr",
        "vol_ann",
        "sharpe",
        "max_drawdown",
    ]

    print(out[display_cols].to_string(index=False, float_format=lambda x: f"{x:0.4f}"))
    print(f"\nSaved summary -> {out_path}")


if __name__ == "__main__":
    main()
