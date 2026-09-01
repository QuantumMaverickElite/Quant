# Market Intelligence v1.5

v1.5 recalibrates regime-break scoring.

## Why

The first live run showed:

```text
PLTR trend_damage=0.8596
PLTR regime_break_score=0.0422
```

That was too timid. Strong trend damage should force at least caution even when news is neutral or mildly positive.

## Changes

- Adds `price_action_risk` to model features.
- Gives price action enough weight to influence `regime_break_score`.
- Uses a blended price score from:
  - `peer_divergence`
  - `volume_shock`
  - `trend_damage`

The engine still does not trade directly. It now gives price damage a louder vote in the evidence stack.
