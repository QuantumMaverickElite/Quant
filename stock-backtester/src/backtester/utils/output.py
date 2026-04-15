from pathlib import Path
from datetime import datetime


def get_output_dir(strategy: str, ticker: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    base = Path("outputs") / strategy / ticker / timestamp
    base.mkdir(parents=True, exist_ok=True)

    return base


def get_output_paths(strategy: str, ticker: str):
    base = get_output_dir(strategy, ticker)

    return {
        "dir": base,
        "plot": base / "equity_curve.png",
        "data": base / "backtest.csv",
        "trades": base / "trades.csv",
    }
