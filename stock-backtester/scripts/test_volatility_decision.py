import pandas as pd

from backtester.decision.volatility_decision import add_volatility_decisions


def main() -> None:
    df = pd.DataFrame(
        {
            "vol_regime": ["LOW", "NORMAL", "HIGH", "HIGH"],
            "vol_zscore": [-1.4, 0.2, 1.8, 2.8],
            "vol_percentile": [0.15, 0.45, 0.85, 0.97],
            "vol_spike_flag": [False, False, False, True],
        }
    )

    out = add_volatility_decisions(df)

    print(
        out[
            [
                "vol_regime",
                "vol_zscore",
                "vol_percentile",
                "vol_spike_flag",
                "decision_vol_regime",
                "risk_multiplier",
                "preferred_strategy",
                "allow_options",
                "allow_new_equity_positions",
            ]
        ]
    )


if __name__ == "__main__":
    main()
