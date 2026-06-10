from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply market-cap as an additive ranking bonus."
    )

    p.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    p.add_argument(
        "--market-caps",
        default="outputs/cache/market_caps/market_caps_context_adjusted_signal_tickers.csv",
    )
    p.add_argument(
        "--out",
        default="outputs/signals/mean_reversion_signals_market_cap_rank_bonus.parquet",
    )

    p.add_argument("--tier-3-bonus", type=float, default=0.0025)
    p.add_argument("--tier-4-bonus", type=float, default=0.0050)
    p.add_argument("--tier-5-bonus", type=float, default=0.0075)
    p.add_argument("--min-original-confidence", type=float, default=0.10)

    return p.parse_args()


def normalize_ticker(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.strip().str.replace(".", "-", regex=False)


def market_cap_tier(market_cap: pd.Series) -> pd.Series:
    cap = pd.to_numeric(market_cap, errors="coerce")

    return pd.Series(
        np.select(
            [
                cap < 25e9,
                (cap >= 25e9) & (cap < 100e9),
                (cap >= 100e9) & (cap < 250e9),
                (cap >= 250e9) & (cap < 500e9),
                (cap >= 500e9) & (cap < 1e12),
                cap >= 1e12,
            ],
            [0, 1, 2, 3, 4, 5],
            default=np.nan,
        ),
        index=market_cap.index,
        dtype="float64",
    )


def rank_bonus_from_tier(tier: pd.Series, args: argparse.Namespace) -> pd.Series:
    mapping = {
        0: 0.0000,
        1: 0.0000,
        2: 0.0000,
        3: args.tier_3_bonus,
        4: args.tier_4_bonus,
        5: args.tier_5_bonus,
    }

    return tier.map(mapping).fillna(0.0000)


def main() -> None:
    args = parse_args()

    signals = pd.read_parquet(args.signals).copy()
    caps = pd.read_csv(args.market_caps).copy()

    required_signal_cols = ["ticker", "adjusted_confidence"]
    missing = [c for c in required_signal_cols if c not in signals.columns]
    if missing:
        raise ValueError(f"Signals missing required columns: {missing}")

    if "ticker" not in caps.columns or "market_cap" not in caps.columns:
        raise ValueError("Market-cap cache must contain ticker and market_cap columns.")

    signals["ticker"] = normalize_ticker(signals["ticker"])
    caps["ticker"] = normalize_ticker(caps["ticker"])
    caps["market_cap"] = pd.to_numeric(caps["market_cap"], errors="coerce")

    out = signals.merge(
        caps[["ticker", "market_cap"]],
        on="ticker",
        how="left",
    )

    old = out["adjusted_confidence"].astype(float)

    out["market_cap_missing"] = out["market_cap"].isna()
    out["market_cap_tier"] = market_cap_tier(out["market_cap"])

    raw_bonus = rank_bonus_from_tier(out["market_cap_tier"], args)

    eligible = old.ge(args.min_original_confidence) & out["market_cap"].notna()

    out["market_cap_rank_bonus"] = 0.0
    out.loc[eligible, "market_cap_rank_bonus"] = raw_bonus.loc[eligible]

    out["adjusted_confidence_original_context"] = old

    out["adjusted_confidence"] = (old + out["market_cap_rank_bonus"]).clip(0.0, 1.0)

    out["confidence_delta_market_cap_rank_bonus"] = (
        out["adjusted_confidence"] - out["adjusted_confidence_original_context"]
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)

    print(f"Loaded signals:     {args.signals}")
    print(f"Loaded market caps: {args.market_caps}")
    print(f"Saved:              {out_path}")
    print(f"Shape:              {out.shape}")

    print()
    print("Market-cap coverage:")
    print(out["market_cap_missing"].value_counts(dropna=False).to_string())

    print()
    print("Rows by market-cap tier:")
    print(out["market_cap_tier"].value_counts(dropna=False).sort_index().to_string())

    print()
    print("Delta summary:")
    print(out["confidence_delta_market_cap_rank_bonus"].describe().round(6).to_string())

    print()
    print("Rows boosted:", (out["confidence_delta_market_cap_rank_bonus"] > 0).sum())
    print("Rows unchanged:", (out["confidence_delta_market_cap_rank_bonus"] == 0).sum())

    print()
    print("Mean bonus by market-cap tier:")
    print(
        out.groupby("market_cap_tier", dropna=False)[
            "confidence_delta_market_cap_rank_bonus"
        ]
        .agg(["count", "mean", "median", "min", "max"])
        .round(6)
        .to_string()
    )


if __name__ == "__main__":
    main()
