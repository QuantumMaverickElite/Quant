# Known Limitations

This is a research framework, not a production trading system.

Important limitations:

```text
Data currently comes mostly from yfinance.
Slippage and market impact are not fully modeled.
Transaction costs are not fully modeled in all allocator paths.
Options overlay logic is simplified and experimental.
Dividend capture logic is a naive baseline.
The current allocator is not a finished multi-alpha model.
Current universes can be biased toward personally selected stocks and past winners.
Broad-universe validation is still required.
Lookahead bias and selection bias still need explicit audit tools.
```

## Universe Bias

Many current experiments use a small universe that includes personally liked stocks and past winners.

This can create selection bias.

Future experiments should test:

```text
broader universes
less hand-picked stock lists
sector-balanced universes
market-wide universes
randomized universes
out-of-sample periods
```

## Lookahead Bias

Lookahead bias still needs explicit audit tooling.

The project should verify that every signal uses only information available as of the simulated date.

## Data Quality

`yfinance` is useful for research, but it is not institutional-grade.

Future serious validation may require better data.
