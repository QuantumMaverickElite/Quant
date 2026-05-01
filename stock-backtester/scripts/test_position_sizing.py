import pandas as pd

from backtester.decision.position_sizing import apply_route_risk_scaling


def main() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="D")

    positions = pd.Series([1.0, 1.0, 1.0, 0.0], index=idx, name="base_position")

    routes = pd.DataFrame(
        {
            "route_risk_multiplier": [1.0, 0.7, 0.35, 1.0],
        },
        index=idx,
    )

    scaled = apply_route_risk_scaling(positions, routes)

    out = pd.DataFrame(
        {
            "base_position": positions,
            "route_risk_multiplier": routes["route_risk_multiplier"],
            "scaled_position": scaled,
        }
    )

    print(out)


if __name__ == "__main__":
    main()
