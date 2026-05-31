# Entropy Engine

The entropy engine measures uncertainty in returns.

It currently uses two major ideas:

```text
Return entropy:
    How dispersed or abnormal return magnitudes are.

Directional entropy:
    How choppy or random the up/down sequence is.
```

## Regimes

Entropy regimes include:

```text
LOW
NORMAL
HIGH
EXTREME
```

The system can also combine return entropy and directional entropy into composite states such as:

```text
RETURN_NORMAL_DIRECTION_NORMAL
RETURN_HIGH_DIRECTION_LOW
RETURN_EXTREME_DIRECTION_NORMAL
RETURN_HIGH_DIRECTION_EXTREME
```

## Decision Layer

The entropy decision layer can produce:

```text
signal_trust_multiplier
allow_new_signals
entropy_state_description
reason
```

The allocator uses `signal_trust_multiplier` to decide how much it should trust raw momentum or strategy scores.

## Why It Matters

High entropy can mean signals are less trustworthy.

Low directional entropy can mean movement is more ordered.

High directional entropy can mean price action is more random or choppy.

The allocator can use this information to reduce exposure, block new signals, or change strategy preferences.
