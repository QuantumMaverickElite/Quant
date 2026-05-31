# Allocator Findings

The allocator currently behaves more like a defensive momentum allocator than a pure alpha maximizer.

## Current Findings

In strong bull markets:

```text
equal-weight and buy-and-hold benchmarks can outperform
because the allocator may hold too much cash or reduce exposure too aggressively
```

In rough or mixed markets:

```text
the allocator can become more competitive
because it reduces drawdowns and improves risk-adjusted behavior
```

## Current Weakness

The current allocator may not press hard enough during risk-on environments.

The key research question is:

```text
How do we make the allocator adaptive enough to press harder in bull regimes
while preserving defensive behavior in unstable regimes?
```

## Future Direction

The future allocator should combine many signals:

```text
momentum
volatility
entropy
correlation
drawdown behavior
regime sensitivity
dividend events
buybacks
splits
earnings behavior
liquidity
sector or cluster exposure
macro/rate sensitivity
```

The allocator should not simply pick the highest-scoring stocks.

It should decide:

```text
Which signals matter right now?
How correlated are these candidates?
How much exposure should the portfolio take?
What risks are hidden in this basket?
Should the system press risk-on or defend capital?
```
