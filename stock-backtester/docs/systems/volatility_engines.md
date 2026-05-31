# Volatility Engines

The project uses two volatility concepts:

```text
GARCH volatility
Fast realized-volatility proxy
```

## GARCH Volatility

GARCH volatility is model-based. It attempts to estimate conditional volatility using recent shocks and recent volatility behavior.

It is useful for:

```text
deeper volatility analysis
regime validation
studying volatility clustering
smaller-universe research
```

But it is slower and can be fragile in large loops because it requires repeated model fitting.

## Fast Volatility

Fast volatility is a rolling-statistics proxy.

It uses:

```text
realized volatility
rolling z-scores
volatility percentiles
spike flags
```

It is useful for:

```text
broad universe scans
feature matrix construction
fast Monte Carlo simulations
future CUDA/CuPy acceleration
```

## Research Role

Fast volatility is the preferred scalable path.

GARCH remains useful as a deeper validation mode for smaller selected universes.
