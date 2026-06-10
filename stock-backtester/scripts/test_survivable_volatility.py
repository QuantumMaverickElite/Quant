import pandas as pd

from src.features.survivable_volatility import compute_survivable_volatility


def make_same_shock_test() -> pd.DataFrame:
    """
    Same volatility event across different company sizes.

    This tests the core thesis:
    the same drawdown/vol spike should be treated as more survivable
    for larger, more institutionally durable companies.
    """

    market_cap_cases = [
        ("small_cap", 10e9),
        ("mid_cap", 75e9),
        ("large_cap", 150e9),
        ("major_large_cap", 350e9),
        ("mega_cap", 750e9),
        ("ultra_mega_cap", 1.5e12),
    ]

    rows = []

    for label, market_cap in market_cap_cases:
        rows.append(
            {
                "case": label,
                "market_cap": market_cap,
                "vol_z": 1.75,
                "drawdown": -0.12,
                "confidence": 0.50,
                "close": 100,
                "sma_50": 98,
                "sma_200": 90,
                "distance_from_52w_high": -0.12,
            }
        )

    return pd.DataFrame(rows)


def make_trend_damage_test() -> pd.DataFrame:
    """
    Tests that mega-cap size alone does not blindly override a broken trend.
    """

    return pd.DataFrame(
        [
            {
                "case": "mega_cap_healthy_pullback",
                "market_cap": 1.2e12,
                "vol_z": 1.50,
                "drawdown": -0.12,
                "confidence": 0.55,
                "close": 100,
                "sma_50": 98,
                "sma_200": 90,
                "distance_from_52w_high": -0.12,
            },
            {
                "case": "mega_cap_broken_trend",
                "market_cap": 1.2e12,
                "vol_z": 2.25,
                "drawdown": -0.35,
                "confidence": 0.55,
                "close": 100,
                "sma_50": 115,
                "sma_200": 130,
                "distance_from_52w_high": -0.38,
            },
        ]
    )


def show_results(df: pd.DataFrame, title: str) -> None:
    out = compute_survivable_volatility(df)

    cols = [
        "case",
        "market_cap_tier",
        "cap_tolerance_multiplier",
        "trend_quality_score",
        "exit_pressure_raw",
        "exit_pressure_adjusted",
        "size_permission_multiplier",
        "dip_buy_permission",
        "confidence_survivable_vol_adjusted",
    ]

    print(f"\n{title}")
    print("=" * len(title))
    print(out[cols].round(4).to_string(index=False))


def main() -> None:
    show_results(
        make_same_shock_test(),
        "Same Volatility Shock Across Market-Cap Tiers",
    )

    show_results(
        make_trend_damage_test(),
        "Mega-Cap Pullback vs Mega-Cap Broken Trend",
    )


if __name__ == "__main__":
    main()
