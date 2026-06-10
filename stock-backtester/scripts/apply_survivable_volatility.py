from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features.survivable_volatility import compute_survivable_volatility

INPUT_PATH = Path("outputs/signals/mean_reversion_signals_context_adjusted.parquet")
OUTPUT_PATH = Path("outputs/signals/mean_reversion_signals_survivable_vol.parquet")
PRICE_FEATURE_PATH = Path("outputs/features/survivable_vol_price_features.parquet")


def add_temporary_market_caps(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Temporary v1 market-cap map.

    This lets us test the survivable-volatility pipeline immediately.
    Later, replace this with a real historical/daily market-cap merge.
    """

    cap_map = {
        "AAPL": 3.0e12,
        "MSFT": 3.2e12,
        "NVDA": 3.0e12,
        "GOOGL": 2.0e12,
        "GOOG": 2.0e12,
        "AMZN": 1.9e12,
        "META": 1.3e12,
        "TSLA": 1.3e12,
        "AVGO": 1.7e12,
        "ORCL": 6.0e11,
        "JPM": 5.5e11,
        "WMT": 6.0e11,
        "COST": 4.0e11,
        "LLY": 8.0e11,
        "BRK.B": 9.0e11,
        "BRK-B": 9.0e11,
        "UNH": 4.5e11,
        "V": 7.0e11,
        "MA": 4.5e11,
        "HD": 3.5e11,
        "BAC": 3.0e11,
        "XOM": 5.0e11,
        "CVX": 3.0e11,
        "JNJ": 3.5e11,
        "ABBV": 3.0e11,
        "PFE": 1.5e11,
        "MRK": 2.5e11,
        "WFC": 2.5e11,
        "MS": 1.5e11,
        "GS": 1.8e11,
        "AMD": 2.5e11,
        "PLTR": 3.0e11,
    }

    out = signals.copy()
    out["market_cap"] = out["ticker"].map(cap_map)

    # Neutral default for unknown tickers.
    # This avoids crashing but does not give unknown names mega-cap forgiveness.
    out["market_cap"] = out["market_cap"].fillna(75e9)

    return out


def merge_price_features(signals: pd.DataFrame) -> pd.DataFrame:
    price_features = pd.read_parquet(PRICE_FEATURE_PATH)

    out = signals.copy()
    out["date"] = pd.to_datetime(out["date"])
    price_features["date"] = pd.to_datetime(price_features["date"])

    merge_cols = [
        "date",
        "ticker",
        "close",
        "sma_50",
        "sma_200",
        "drawdown",
        "distance_from_52w_high",
    ]

    out = out.merge(
        price_features[merge_cols],
        on=["date", "ticker"],
        how="left",
    )

    return out


def prepare_survivable_vol_inputs(signals: pd.DataFrame) -> pd.DataFrame:
    out = signals.copy()

    if "realized_vol_z" in out.columns:
        out["vol_z"] = out["realized_vol_z"]
    else:
        out["vol_z"] = 0.0

    # Temporary neutral drawdown until we merge price features.
    if "drawdown" not in out.columns:
        out["drawdown"] = 0.0

    # Temporary neutral trend fields.
    # These prevent trend_quality_score from becoming overly opinionated.
    if "close" not in out.columns:
        out["close"] = 100.0

    if "sma_50" not in out.columns:
        out["sma_50"] = 100.0

    if "sma_200" not in out.columns:
        out["sma_200"] = 100.0

    if "distance_from_52w_high" not in out.columns:
        out["distance_from_52w_high"] = 0.0

    return out


def main() -> None:
    signals = pd.read_parquet(INPUT_PATH)

    signals = add_temporary_market_caps(signals)
    signals = merge_price_features(signals)
    signals = prepare_survivable_vol_inputs(signals)

    out = compute_survivable_volatility(
        signals,
        market_cap_col="market_cap",
        vol_z_col="vol_z",
        drawdown_col="drawdown",
        base_confidence_col="confidence",
    )

    # Preserve old adjusted confidence for comparison.
    out["adjusted_confidence_old"] = out["adjusted_confidence"]

    # New context confidence:
    # keep entropy_weight, but replace old volatility treatment with survivable-vol adjustment.
    if "entropy_weight" in out.columns:
        out["adjusted_confidence_survivable_vol"] = (
            out["confidence_survivable_vol_adjusted"] * out["entropy_weight"]
        ).clip(0.0, 1.0)
    else:
        out["adjusted_confidence_survivable_vol"] = (
            out["confidence_survivable_vol_adjusted"]
        ).clip(0.0, 1.0)

    out["confidence_delta_survivable_vol"] = (
        out["adjusted_confidence_survivable_vol"] - out["adjusted_confidence_old"]
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_PATH, index=False)

    print(f"Loaded: {INPUT_PATH}")
    print(f"Saved:  {OUTPUT_PATH}")
    print(f"Shape:  {out.shape}")

    summary_cols = [
        "ticker",
        "horizon",
        "direction",
        "confidence",
        "adjusted_confidence_old",
        "adjusted_confidence_survivable_vol",
        "confidence_delta_survivable_vol",
        "market_cap",
        "market_cap_tier",
        "cap_tolerance_multiplier",
        "realized_vol_z",
        "exit_pressure_adjusted",
        "size_permission_multiplier",
        "dip_buy_permission",
    ]

    print()
    print("Top positive confidence changes:")
    print(
        out.sort_values("confidence_delta_survivable_vol", ascending=False)[
            summary_cols
        ]
        .head(20)
        .round(4)
        .to_string(index=False)
    )

    print()
    print("Top negative confidence changes:")
    print(
        out.sort_values("confidence_delta_survivable_vol", ascending=True)[summary_cols]
        .head(20)
        .round(4)
        .to_string(index=False)
    )

    print()
    print("Market-cap tier counts:")
    print(out["market_cap_tier"].value_counts(dropna=False).sort_index().to_string())

    print()
    print("Confidence delta summary:")
    print(out["confidence_delta_survivable_vol"].describe().round(6).to_string())


if __name__ == "__main__":
    main()
