from __future__ import annotations

from pathlib import Path

import pandas as pd

PRICE_PATH = Path(
    "outputs/feature_matrix/market_state_2018_2026_quality/close_prices.csv"
)
OUTPUT_PATH = Path("outputs/features/survivable_vol_price_features.parquet")


def main() -> None:
    prices = pd.read_csv(PRICE_PATH)

    date_col = prices.columns[0]
    prices = prices.rename(columns={date_col: "date"})
    prices["date"] = pd.to_datetime(prices["date"])

    long_prices = prices.melt(
        id_vars="date",
        var_name="ticker",
        value_name="close",
    )

    long_prices = long_prices.dropna(subset=["close"])
    long_prices = long_prices.sort_values(["ticker", "date"])

    grouped = long_prices.groupby("ticker", group_keys=False)

    long_prices["sma_50"] = grouped["close"].transform(
        lambda s: s.rolling(50, min_periods=25).mean()
    )

    long_prices["sma_200"] = grouped["close"].transform(
        lambda s: s.rolling(200, min_periods=100).mean()
    )

    long_prices["high_52w"] = grouped["close"].transform(
        lambda s: s.rolling(252, min_periods=126).max()
    )

    long_prices["drawdown"] = (long_prices["close"] / long_prices["high_52w"]) - 1.0
    long_prices["distance_from_52w_high"] = long_prices["drawdown"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    long_prices.to_parquet(OUTPUT_PATH, index=False)

    print(f"Loaded: {PRICE_PATH}")
    print(f"Saved:  {OUTPUT_PATH}")
    print(f"Shape:  {long_prices.shape}")
    print(long_prices.head().to_string())


if __name__ == "__main__":
    main()
