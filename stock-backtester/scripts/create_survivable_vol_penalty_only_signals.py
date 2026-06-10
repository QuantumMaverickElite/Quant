from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

INPUT_PATH = Path("outputs/signals/mean_reversion_signals_survivable_vol.parquet")
OUTPUT_PATH = Path(
    "outputs/signals/mean_reversion_signals_survivable_vol_penalty_only.parquet"
)


def main() -> None:
    df = pd.read_parquet(INPUT_PATH).copy()

    required = [
        "adjusted_confidence_old",
        "size_permission_multiplier",
        "trend_quality_score",
        "price_features_missing",
        "dip_buy_permission",
    ]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    old = df["adjusted_confidence_old"].astype(float)

    # Start neutral.
    penalty = pd.Series(1.0, index=df.index, dtype="float64")

    # Broken trend should hurt.
    penalty *= np.where(df["trend_quality_score"].astype(float) < 0.20, 0.75, 1.0)

    # High adjusted exit pressure already maps into size_permission_multiplier.
    # But cap it so survivable-vol cannot create broad boosts.
    penalty *= np.minimum(df["size_permission_multiplier"].astype(float), 1.0)

    # Missing price structure should never receive a benefit.
    penalty *= np.where(df["price_features_missing"].astype(bool), 0.98, 1.0)

    # Tiny reward only for confirmed dip-buy permission.
    # This is deliberately small.
    bonus = np.where(df["dip_buy_permission"].astype(bool), 1.02, 1.0)

    df["survivable_vol_penalty_only_multiplier"] = penalty * bonus
    df["adjusted_confidence_original_context"] = old

    df["adjusted_confidence"] = (
        old * df["survivable_vol_penalty_only_multiplier"]
    ).clip(0.0, 1.0)

    df["confidence_delta_survivable_vol_penalty_only"] = df["adjusted_confidence"] - old

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)

    print(f"Loaded: {INPUT_PATH}")
    print(f"Saved:  {OUTPUT_PATH}")
    print(f"Shape:  {df.shape}")
    print()
    print(
        df["confidence_delta_survivable_vol_penalty_only"]
        .describe()
        .round(6)
        .to_string()
    )
    print()
    print(
        "Rows boosted:", (df["confidence_delta_survivable_vol_penalty_only"] > 0).sum()
    )
    print(
        "Rows unchanged-ish:",
        (df["confidence_delta_survivable_vol_penalty_only"].abs() < 0.005).sum(),
    )
    print(
        "Rows penalized:",
        (df["confidence_delta_survivable_vol_penalty_only"] < 0).sum(),
    )


if __name__ == "__main__":
    main()
