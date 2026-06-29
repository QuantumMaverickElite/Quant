# Target Architecture

The goal is not to rewrite the project. The goal is to turn the current script-heavy research repo into a stable research operating system.

## Current problem

The project currently has several types of code mixed together:

- production-ish reusable modules under `src/backtester`
- many top-level scripts under `scripts`
- repeated market-intelligence overlay directories
- old generated CSV/JSON artifacts
- docs that act like version history
- visual experiments and archive outputs

## Target structure

```text
src/backtester/
  core/
    interfaces.py
    registry.py
    schemas.py

  math_core/
    state_space/
    spectral/
    graph/
    volatility/
    regimes/
    point_processes/
    optimal_transport/
    generative/
    signal_algebra/
    allocation/

  finance/
    data/
    features/
    signals/
    intelligence/
    risk/
    portfolio/
    options/
    execution/

  research/
    experiments/
    evaluation/
    reports/

scripts/
  wrappers first, then organized command groups later

docs/
  architecture/
  systems/
  research/
  experiments/
  changelog/
  reorg/
```

## Compatibility policy

Old commands remain valid until explicitly deprecated.

A moved script should leave behind a wrapper:

```python
from backtester.finance.signals.commands.run_mean_reversion_signals import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## Mathematical module rule

Every new mathematical idea must expose a stable interface:

- inputs
- outputs
- metadata
- reproducibility configuration
- evaluation hook

This applies to Kalman, RMT, Wasserstein, Cox, SABR, GAN/VAEs, HMMs, entropy, HRP, and future research modules.
