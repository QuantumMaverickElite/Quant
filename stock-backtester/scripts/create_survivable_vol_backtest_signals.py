from __future__ import annotations

from pathlib import Path

import pandas as pd

INPUT_PATH = Path("outputs/signals/mean_reversion_signals_survivable_vol.parquet")
OUTPUT_PATH = Path(
    "outputs/signals/mean_reversion_signals_survivable_vol_backtest.parquet"
)


def main() -> None:
    df = pd.read_parquet(INPUT_PATH)

    required_cols = [
        "adjusted_confidence",
        "adjusted_confidence_survivable_vol",
    ]

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    out = df.copy()

    out["adjusted_confidence_original_context"] = out["adjusted_confidence"]
    out["adjusted_confidence"] = out["adjusted_confidence_survivable_vol"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_PATH, index=False)

    print(f"Loaded: {INPUT_PATH}")
    print(f"Saved:  {OUTPUT_PATH}")
    print(f"Shape:  {out.shape}")

    print()
    print("Adjusted confidence comparison:")
    print(
        out[
            [
                "adjusted_confidence_original_context",
                "adjusted_confidence",
                "confidence_delta_survivable_vol",
            ]
        ]
        .describe()
        .round(6)
        .to_string()
    )


if __name__ == "__main__":
    main()
