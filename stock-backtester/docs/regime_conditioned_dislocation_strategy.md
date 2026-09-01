# Regime-Conditioned Dislocation Strategy


## Core Idea

The strategy treats volatility as opportunity creation rather than something to avoid.

The workflow is:

```text
stable capital posture
    -> detect market regime
    -> scan/rank broad stock universe
    -> identify securities aligned with desired metrics
    -> enter small on an attractive dislocation
    -> scale opportunistically if the setup improves
    -> sell into recovery / repricing / macro or earnings-driven strength
    -> return capital to the stable posture
    -> wait for the next dislocation
```

The objective is not to predict exact bottoms. It is to preserve dry powder, react to dislocations, and repeatedly recycle capital through strong quantitative setups.

## Heuristics, Not Hard Rules

There is no fixed rule such as:

```text
buy every 10% decline
```

and "double up" does not mean literal doubling.

It means increasing exposure when the opportunity becomes materially more attractive.

Example:

```text
140 -> buy 1
130 -> buy 2 more
109 -> buy 5 more
131 -> sell the full position
```

The exact spacing and sizing are discretionary / heuristic at first.

The important concept is:

> Position size should respond to how attractive the setup becomes, not to a mechanical averaging-down schedule.

A larger allocation at lower prices can pull the weighted-average cost far below the first entry, so the position can become profitable without ever recovering to the original purchase price.

## Why Volatile Regimes Matter

Volatile markets can create repeated short-term price and sentiment dislocations faster than the underlying quantitative quality of a security changes.

The strategy aims to exploit patterns such as:

```text
strong measured profile
    -> broad / sector / idiosyncratic selloff
    -> temporary dislocation
    -> recovery / repricing
```

Instead of forecasting the next geopolitical event, CPI print, earnings reaction, or Fed move, preserve capital and react when volatility creates a favorable setup.

## Do Not Hand-Pick a Small Universe of Known Winners

A major concern is hindsight contamination.

The backtest should not begin with a hand-selected list of companies we already know performed well.

That would risk selecting winners and regimes using future knowledge.

Instead, use a broad point-in-time universe and let the model rank securities by measured characteristics.

At time `t`, the system should only know information that was available at `t`.

The company name or narrative should be irrelevant to the selection process.

Conceptually:

```text
Market State
    -> cross-sectional feature calculation
    -> scoring / ranking
    -> candidate selection
    -> sizing
```

For stock `i` at time `t`:

```text
X_i,t = stock feature vector
R_t   = market regime
S_i,t = score(X_i,t, R_t)
```

Then rank:

```text
S_(1),t > S_(2),t > ... > S_(N),t
```

The ideal system can recommend a stock we do not recognize by name because the decision comes from the measurements, not the story.

## Candidate Feature Families

The exact feature set should be discovered empirically, but likely candidates include:

### Price / Return Structure

- recent returns over multiple horizons
- drawdown from recent highs
- distance from rolling means
- momentum
- reversal / mean-reversion measures
- gap behavior
- overnight vs intraday return structure

### Volatility

- realized volatility
- GARCH-style conditional volatility
- volatility percentile
- volatility z-score
- volatility-of-volatility
- volatility spike indicators
- regime transition measures

### Relative Behavior

- market-relative return
- sector-relative return
- beta-adjusted residual return
- relative strength
- cross-sectional rank

### Liquidity / Trading Activity

- dollar volume
- abnormal volume
- turnover
- liquidity-shock measures
- spread proxies where available

### Fundamental / Quality Metrics

Company stories are irrelevant, but company-level measurements can still be useful features.

Possible inputs:

- revenue growth
- earnings growth
- margins
- free cash flow
- profitability
- leverage
- earnings revisions
- valuation ratios
- balance-sheet strength
- quality composites

These should be numerical inputs, not narrative vetoes.

### Event / Earnings Behavior

- time until earnings
- earnings gap size
- post-earnings drift
- earnings volatility
- revision behavior
- historical reaction to surprises

### Market / Sector Exposure

- beta
- sector beta
- correlation to broad indices
- sector correlation
- factor exposures
- cross-sectional correlation regime

## Market-Regime Layer

The same stock signal may behave differently under different market states.

Possible regime inputs:

- index trend
- realized volatility
- GARCH volatility
- volatility percentile
- breadth
- cross-sectional dispersion
- cross-stock correlation
- rates / rate changes
- credit conditions
- liquidity proxies
- sector dispersion
- entropy / uncertainty measures

The central hypothesis is not simply:

```text
large drawdown -> positive future return
```

but rather:

```text
E[future return | stock characteristics, market regime]
```

or:

```text
P(recovery over horizon k | X_i,t, R_t)
```

The interaction between stock characteristics and regime may matter more than any one feature in isolation.

For example:

```text
drawdown alone                                      -> weak signal
large drawdown + high-volatility regime            -> stronger signal
large drawdown + strong relative metrics + regime  -> potentially stronger signal
```

## Position Sizing Philosophy

This is not intended to be a martingale.

The first position should remain small enough to preserve the ability to add if the opportunity improves.

Conceptually:

```text
exposure = f(
    market regime,
    stock score,
    dislocation magnitude,
    volatility,
    portfolio risk,
    available dry powder
)
```

Future research can compare:

- discrete tranche sizing
- continuous score-based sizing
- volatility scaling
- drawdown scaling
- rank / conviction scaling
- portfolio-risk-constrained sizing
- combinations of the above

## Exit Philosophy

The position does not need to be held indefinitely.

Possible exit signals include:

- recovery toward a recent range
- major positive earnings repricing
- macro relief rally
- dislocation signal normalization
- rank deterioration
- expected-return compression
- a better opportunity elsewhere
- volatility regime normalization

These are candidate rules to test, not fixed rules.

## Main Research Question

The goal is not:

```text
Why did PLTR work?
```

The goal is:

```text
Can a point-in-time, regime-conditioned, cross-sectional process
systematically identify securities likely to recover after large
dislocations without knowing their identities or future outcomes?
```

Potential targets:

```text
P(R_i,t+k > 0 | X_i,t, R_t)
```

and

```text
E[R_i,t+k | X_i,t, R_t]
```

for multiple horizons `k`.

## Backtest Requirements

This strategy is highly vulnerable to look-ahead and survivorship bias.

A serious test should require:

### Point-in-Time Universe

Use securities that were actually eligible at each historical date.

Do not build the universe using only companies that survived to the present.

Include delisted / failed companies where possible.

### Point-in-Time Fundamentals

Fundamental data should enter the model only after it was publicly available.

Do not leak later restatements or future-known values into earlier dates.

### Point-in-Time Events

Earnings dates, guidance, revisions, and event data must respect historical timestamps.

### No Future Normalization

Do not normalize features using the full future sample.

Prefer rolling, expanding-window, or contemporaneous cross-sectional normalization.

### Walk-Forward / Out-of-Sample Evaluation

Use validation and untouched out-of-sample periods, ideally with rolling walk-forward tests.

### Regime Diversity

Test across:

- bull markets
- bear markets
- high-volatility periods
- low-volatility periods
- crash / panic periods
- rate shocks
- sector rotations
- sideways markets

A strategy that only works in one remembered regime is not the target.

## Relationship to the Existing Quant Architecture

This idea fits naturally into the current framework:

```text
price data
    -> feature generation
    -> MarketState / regime logic
    -> cross-sectional scoring
    -> dislocation / opportunity score
    -> allocator / position sizing
    -> portfolio weights
    -> execution
    -> evaluation
```

It can later connect to existing work involving:

- MarketState
- volatility regimes
- entropy
- feature matrices
- deterministic ranking
- allocator research
- Monte Carlo universe sampling
- matrix / GPU experimentation

This should eventually become part of the reproducible research framework rather than a one-off script.

## Possible Future Decomposition

```text
1. Regime Engine
   What state is the market in?

2. Opportunity Engine
   Which stocks are unusually dislocated relative to their measured profile?

3. Cross-Sectional Ranker
   Which candidates have the strongest expected opportunity?

4. Sizing Engine
   How much exposure should each candidate receive?

5. Reassessment Engine
   Did a further decline improve or worsen the opportunity?

6. Exit Engine
   Has the dislocation been harvested or has the rank deteriorated?
```

These components should communicate through explicit numerical state rather than company narratives.

## Key Principle

> Do not try to predict every market shock. Preserve capital, quantify the regime, identify securities whose measured characteristics best align with the objective, and use volatility-driven dislocations as opportunities to deploy and recycle capital.

The strategy should be judged by whether it generalizes to unknown stocks and unseen regimes, not by whether it reproduces a few memorable winning trades.


