from pathlib import Path
from datetime import datetime


def get_output_dir(
    strategy: str,
    ticker: str,
    output_root: Path | str = "outputs",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    base = Path(output_root) / strategy / ticker / timestamp
    base.mkdir(parents=True, exist_ok=True)

    return base


def get_output_paths(
    strategy: str,
    ticker: str,
    output_root: Path | str = "outputs",
) -> dict[str, Path]:
    base = get_output_dir(strategy, ticker, output_root=output_root)

    return {
        "dir": base,
        "plot": base / "equity_curve.png",
        "data": base / "backtest.csv",
        "trades": base / "trades.csv",
    }
