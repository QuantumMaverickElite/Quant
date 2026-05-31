# Strategy Math and Signal Definitions

This document explains the math behind the signals, engines, allocation rules, risk controls, and backtest metrics used in the project.

The goal is to make the project understandable without requiring someone to reverse-engineer the Python code.

---

## 1. Price and Return Math

Let:

- `P_{i,t}` be the price of asset `i` at time `t`
- `r_{i,t}` be the simple return of asset `i` at time `t`
- `ell_{i,t}` be the log return of asset `i` at time `t`
- `w_{i,t}` be the portfolio weight assigned to asset `i` at time `t`
- `N` be the number of assets in the universe

Simple return:

```math
r_{i,t} = \frac{P_{i,t}}{P_{i,t-1}} - 1
```

Log return:

```math
\ell_{i,t} = \log(P_{i,t}) - \log(P_{i,t-1})
```

Portfolio return:

```math
r_{p,t} = \sum_{i=1}^{N} w_{i,t} r_{i,t}
```

Portfolio value:

```math
V_t = V_{t-1}(1 + r_{p,t})
```

---

## 2. Momentum Signals

A momentum signal measures whether an asset has recently been rising or falling.

For a lookback window `k`, the momentum of asset `i` is:

```math
M_{i,t}^{(k)} = \frac{P_{i,t}}{P_{i,t-k}} - 1
```

Interpretation:

- Positive momentum means the asset has gone up over the lookback period.
- Negative momentum means the asset has gone down over the lookback period.
- A simple momentum strategy may rank assets by `M_{i,t}^{(k)}` and select the strongest names.

---

## 3. Mean Reversion Signals

A mean reversion signal measures how far an asset is from its recent average.

Rolling mean:

```math
\mu_{i,t}^{(k)} = \frac{1}{k}\sum_{j=0}^{k-1} P_{i,t-j}
```

Rolling standard deviation:

```math
\sigma_{i,t}^{(k)} =
\sqrt{
\frac{1}{k-1}
\sum_{j=0}^{k-1}
\left(P_{i,t-j} - \mu_{i,t}^{(k)}\right)^2
}
```

Z-score:

```math
z_{i,t}^{(k)} =
\frac{P_{i,t} - \mu_{i,t}^{(k)}}{\sigma_{i,t}^{(k)}}
```

Interpretation:

- `z_{i,t} > 0`: price is above its recent average.
- `z_{i,t} < 0`: price is below its recent average.
- Very negative z-scores may indicate an oversold condition.
- Very positive z-scores may indicate an overbought condition.

A mean reversion strategy may buy assets with low z-scores and reduce exposure to assets with high z-scores.

---

## 4. Volatility Signals

Volatility measures how much an asset moves.

Using returns over a lookback window `k`, rolling volatility is:

```math
\sigma_{i,t}^{(k)} =
\sqrt{
\frac{1}{k-1}
\sum_{j=0}^{k-1}
\left(r_{i,t-j} - \bar{r}_{i,t}^{(k)}\right)^2
}
```

Annualized volatility:

```math
\sigma_{i,t,\text{ann}}^{(k)}
=
\sqrt{252} \cdot \sigma_{i,t}^{(k)}
```

Volatility can be used as:

- a risk penalty
- a regime signal
- a position sizing input
- a trigger for reducing exposure
- a high-volatility opportunity signal

---

## 5. GARCH Volatility Engine

The GARCH engine estimates changing volatility over time.

A common model is GARCH(1,1):

```math
r_t = \mu + \epsilon_t
```

```math
\epsilon_t = \sigma_t z_t
```

```math
\sigma_t^2 =
\omega
+
\alpha \epsilon_{t-1}^2
+
\beta \sigma_{t-1}^2
```

where:

- `sigma_t^2` is the conditional variance at time `t`
- `omega` is the baseline variance level
- `alpha` controls how strongly recent shocks affect volatility
- `beta` controls how persistent volatility is
- `epsilon_{t-1}^2` is the previous squared shock
- `z_t` is usually treated as a standardized random variable

Interpretation:

- A large shock increases future volatility.
- A high `beta` means volatility decays slowly.
- GARCH is useful because market volatility clusters.

The GARCH engine can help decide whether the system should increase exposure, reduce exposure, or route into a different strategy mode.

---

## 6. Entropy Engine

Entropy measures uncertainty, disorder, or unpredictability.

For market states with probabilities `p_1, p_2, ..., p_n`, Shannon entropy is:

```math
H = -\sum_{i=1}^{n} p_i \log(p_i)
```

For binned return states:

```math
H_t =
-\sum_{j=1}^{m}
p_{j,t}\log(p_{j,t})
```

where:

- `p_{j,t}` is the probability of returns falling into bin `j`
- `m` is the number of bins

Interpretation:

- Low entropy means the system is more ordered or predictable.
- High entropy means the system is more uncertain or chaotic.

Possible market interpretations:

- Low entropy plus positive trend may indicate a cleaner momentum environment.
- High entropy plus high volatility may indicate unstable risk conditions.
- Low entropy plus compressed volatility may indicate a possible pre-breakout environment.

---

## 7. Regime Engine

A regime engine classifies the market into different states.

Examples:

- bull regime
- bear regime
- sideways regime
- high-volatility regime
- low-volatility regime
- crisis regime
- recovery regime

A simple regime score can combine trend and volatility:

```math
R_t = aT_t - b\sigma_t
```

where:

- `T_t` is a trend signal
- `sigma_t` is volatility
- `a` and `b` are weights

A simple trend signal can be:

```math
T_t =
\frac{P_t}{MA_t^{(k)}} - 1
```

where `MA_t^{(k)}` is a moving average.

Example classification rule:

```math
\text{Regime}_t =
\begin{cases}
\text{Bull}, & T_t > 0 \text{ and } \sigma_t < \sigma_{\text{high}} \\
\text{Volatile Bull}, & T_t > 0 \text{ and } \sigma_t \geq \sigma_{\text{high}} \\
\text{Bear}, & T_t < 0 \text{ and } \sigma_t < \sigma_{\text{high}} \\
\text{Crisis}, & T_t < 0 \text{ and } \sigma_t \geq \sigma_{\text{high}}
\end{cases}
```

The regime engine allows the strategy to behave differently depending on market conditions.

For example:

- In a bull regime, the system may allow higher equity exposure.
- In a bear regime, the system may reduce exposure.
- In a crisis regime, the system may use stricter risk controls.
- In a sideways regime, the system may favor mean reversion instead of momentum.

---

## 8. Correlation Engine

The correlation engine measures how similarly assets move.

For assets `i` and `j`, rolling correlation is:

```math
\rho_{ij,t}^{(k)}
=
\frac{\text{Cov}(r_i, r_j)}
{\sigma_i \sigma_j}
```

Interpretation:

- `rho` near `1`: assets move together
- `rho` near `0`: assets are mostly unrelated
- `rho` near `-1`: assets move in opposite directions

Average portfolio correlation:

```math
\bar{\rho}_t =
\frac{2}{N(N-1)}
\sum_{i<j} \rho_{ij,t}
```

A high average correlation may indicate that diversification is weakening.

---

## 9. High-Volatility Engine

The high-volatility engine looks for situations where volatility itself may create opportunity.

A volatility z-score can compare current volatility to recent volatility:

```math
z_{\sigma,t}
=
\frac{\sigma_t - \mu_{\sigma,t}^{(k)}}
{\sigma_{\sigma,t}^{(k)}}
```

Interpretation:

- High `z_{sigma,t}` means volatility is unusually high.
- Low `z_{sigma,t}` means volatility is unusually low.

A high-volatility mean reversion setup may require both high volatility and an oversold price:

```math
z_{\sigma,t} > c
```

```math
z_{price,t} < -d
```

This means volatility is unusually high and price is unusually low.

---

## 10. Volatility Router

A volatility router changes strategy behavior depending on volatility conditions.

Example routing rule:

```math
\text{Route}_t =
\begin{cases}
\text{Normal Strategy}, & \sigma_t < \sigma_{\text{medium}} \\
\text{Reduced Exposure}, & \sigma_{\text{medium}} \leq \sigma_t < \sigma_{\text{high}} \\
\text{Extreme Risk Mode}, & \sigma_t \geq \sigma_{\text{high}}
\end{cases}
```

The router does not necessarily create a signal by itself. Instead, it decides which behavior should be active.

For example:

- Low volatility: allow normal allocation.
- Medium volatility: reduce position sizes.
- High volatility: use defensive rules.
- Extreme volatility: only trade if the opportunity is very strong.

---

## 11. Dividend Signal

A dividend signal can rank assets based on dividend-related events or yield.

Dividend yield:

```math
DY_{i,t} =
\frac{D_{i,t}}{P_{i,t}}
```

where:

- `D_{i,t}` is annual dividend per share
- `P_{i,t}` is price

A simplified dividend event return can be written as:

```math
R_{\text{event}}
=
\frac{P_{\text{sell}} + D - P_{\text{buy}}}
{P_{\text{buy}}}
```

where:

- `P_buy` is the entry price
- `P_sell` is the exit price
- `D` is the dividend received

This type of signal is event-driven rather than purely technical.

---

## 12. Buyback Signal

A buyback signal attempts to capture the effect of companies repurchasing their own shares.

A simple buyback yield can be estimated as:

```math
BY_{i,t}
=
\frac{\text{Net Buybacks}_{i,t}}
{\text{Market Cap}_{i,t}}
```

Buybacks can matter because reducing share count may increase ownership concentration and earnings per share.

The signal may become stronger when buybacks are large relative to market capitalization.

---

## 13. Stock Split Signal

A stock split signal is event-driven.

For a split ratio `a:b`, the adjusted price is:

```math
P_{\text{after}}
=
P_{\text{before}}
\cdot
\frac{b}{a}
```

The market value of the position does not mechanically change from the split itself.

However, splits may affect:

- liquidity
- retail accessibility
- market attention
- post-event momentum

A split signal should therefore be treated as an event signal, not as guaranteed alpha.

---

## 14. Options Overlay

The options overlay is conditional.

It should not always be active. Instead, it should depend on the state of the underlying asset, volatility, and the strategy signal.

A simplified options permission rule may look like:

```math
O_t =
\begin{cases}
1, & \text{signal strength} > c \text{ and volatility condition is favorable} \\
0, & \text{otherwise}
\end{cases}
```

where `O_t = 1` means the options overlay is allowed.

The options overlay can be used to express stronger conviction, hedge risk, or create asymmetric exposure.

Because options introduce nonlinear payoff behavior, they should be treated separately from ordinary equity exposure.

---

## 15. Signal Normalization

Different signals may have different scales.

Examples:

- momentum may be measured in percent return
- volatility may be measured as standard deviation
- entropy may be measured using probabilities
- correlation may range from `-1` to `1`

Z-score normalization:

```math
x_{i,t}^{norm}
=
\frac{x_{i,t} - \mu_t(x)}
{\sigma_t(x)}
```

Rank normalization:

```math
x_{i,t}^{rank}
=
\frac{\text{rank}(x_{i,t})}{N}
```

Normalization allows different signals to be combined into one score more safely.

---

## 16. Composite Scoring Model

A composite score combines multiple signals.

Example:

```math
S_{i,t}
=
\alpha_1 M_{i,t}
+
\alpha_2 MR_{i,t}
+
\alpha_3 D_{i,t}
+
\alpha_4 B_{i,t}
-
\alpha_5 \sigma_{i,t}
-
\alpha_6 C_{i,t}
```

where:

- `S_{i,t}` is the total score for asset `i`
- `M_{i,t}` is momentum
- `MR_{i,t}` is mean reversion
- `D_{i,t}` is dividend score
- `B_{i,t}` is buyback score
- `sigma_{i,t}` is volatility
- `C_{i,t}` is concentration or correlation penalty
- `alpha_j` are signal weights

The scoring model is important because the long-term goal is not only to test isolated strategies, but to build a system that can compare and rotate between opportunities.

---

## 17. Top-K Selection

A simple allocator may select the top `k` assets by score.

```math
\text{Selected}_t = \text{TopK}(S_{i,t})
```

Equal-weight allocation:

```math
w_{i,t} =
\begin{cases}
\frac{1}{k}, & i \in \text{Selected}_t \\
0, & \text{otherwise}
\end{cases}
```

This is simple and interpretable, but it may ignore differences in conviction, volatility, and correlation.

---

## 18. Score-Weighted Allocation

A score-weighted allocator assigns more capital to higher-scoring assets.

```math
w_{i,t}
=
\frac{\max(S_{i,t}, 0)}
{\sum_{j=1}^{N} \max(S_{j,t}, 0)}
```

This only gives weight to assets with positive scores.

A more conservative version may apply a maximum position size:

```math
w_{i,t} \leq w_{\max}
```

---

## 19. Volatility-Adjusted Allocation

A volatility-adjusted allocator gives less weight to more volatile assets.

Raw volatility-adjusted weight:

```math
\tilde{w}_{i,t}
=
\frac{S_{i,t}}{\sigma_{i,t}}
```

Normalized final weight:

```math
w_{i,t}
=
\frac{\max(\tilde{w}_{i,t}, 0)}
{\sum_{j=1}^{N} \max(\tilde{w}_{j,t}, 0)}
```

This rewards high score but penalizes high risk.

---

## 20. Correlation-Aware Allocation

A correlation-aware allocator reduces concentration in highly correlated assets.

One possible penalty:

```math
Penalty_{i,t}
=
\frac{1}{k}
\sum_{j \in Portfolio}
\rho_{ij,t}
```

Adjusted score:

```math
S_{i,t}^{adj}
=
S_{i,t}
-
\lambda Penalty_{i,t}
```

where `lambda` controls how strongly correlation is penalized.

This helps prevent the portfolio from accidentally becoming concentrated in one theme, sector, or risk factor.

---

## 21. Threshold Rebalancing

Threshold rebalancing avoids trading unless portfolio weights drift far enough from target weights.

Let:

- `w_{i,t}^{actual}` be the current actual weight
- `w_{i,t}^{target}` be the desired target weight
- `theta` be the rebalance threshold

Rebalance condition:

```math
\left|
w_{i,t}^{actual}
-
w_{i,t}^{target}
\right|
>
\theta
```

If the difference is smaller than the threshold, the portfolio does not trade.

This can reduce turnover, transaction costs, and unnecessary trading.

---

## 22. Risk Scaling

Risk scaling changes total exposure based on market conditions.

Example:

```math
E_t =
\begin{cases}
1.00, & \text{low risk} \\
0.75, & \text{medium risk} \\
0.50, & \text{high risk} \\
0.25, & \text{extreme risk}
\end{cases}
```

Final weight:

```math
w_{i,t}^{final}
=
E_t \cdot w_{i,t}^{target}
```

Cash weight:

```math
w_{cash,t}
=
1
-
\sum_i w_{i,t}^{final}
```

Risk scaling allows the system to stay invested during favorable conditions and reduce exposure during dangerous conditions.

---

## 23. Transaction Costs

Transaction costs reduce portfolio value when trades occur.

Turnover:

```math
TO_t =
\sum_i
\left|
w_{i,t}^{new}
-
w_{i,t}^{old}
\right|
```

Cost:

```math
Cost_t
=
c \cdot TO_t \cdot V_t
```

Portfolio value after costs:

```math
V_t^{after}
=
V_t^{before}
-
Cost_t
```

Transaction costs are important because a strategy can look good before costs but fail after realistic trading friction.

---

## 24. Slippage

Slippage measures the difference between expected execution price and actual execution price.

For a buy order:

```math
Slippage_{\text{buy}}
=
\frac{P_{\text{actual}} - P_{\text{expected}}}
{P_{\text{expected}}}
```

For a sell order:

```math
Slippage_{\text{sell}}
=
\frac{P_{\text{expected}} - P_{\text{actual}}}
{P_{\text{expected}}}
```

Slippage is especially important for:

- small-cap stocks
- high-volatility stocks
- large orders
- low-liquidity assets
- fast-moving markets

---

## 25. CAGR

Compound annual growth rate measures annualized return.

```math
CAGR
=
\left(
\frac{V_T}{V_0}
\right)^{1/Y}
-
1
```

where:

- `V_T` is final portfolio value
- `V_0` is starting portfolio value
- `Y` is the number of years

---

## 26. Portfolio Volatility

Daily portfolio volatility:

```math
\sigma_p
=
std(r_{p,t})
```

Annualized portfolio volatility:

```math
\sigma_{p,\text{ann}}
=
\sqrt{252}
\cdot
\sigma_p
```

---

## 27. Sharpe Ratio

Sharpe ratio measures return per unit of volatility.

```math
Sharpe
=
\frac{\mathbb{E}[r_p - r_f]}
{\sigma_p}
```

Annualized Sharpe using daily returns:

```math
Sharpe_{\text{ann}}
=
\frac{\bar{r}_p - \bar{r}_f}
{\sigma_p}
\sqrt{252}
```

where:

- `r_p` is portfolio return
- `r_f` is risk-free return
- `sigma_p` is volatility of portfolio returns

---

## 28. Maximum Drawdown

Drawdown measures decline from a previous peak.

Running peak:

```math
Peak_t =
\max_{\tau \leq t}
V_{\tau}
```

Drawdown:

```math
DD_t
=
\frac{V_t - Peak_t}
{Peak_t}
```

Maximum drawdown:

```math
MDD =
\min_t DD_t
```

Maximum drawdown is one of the most important risk metrics because it shows the worst peak-to-trough loss.

---

## 29. Win Rate

Win rate measures the percentage of profitable trades.

```math
WinRate
=
\frac{\text{Number of Winning Trades}}
{\text{Total Number of Trades}}
```

Win rate alone is not enough. A strategy can have a high win rate and still lose money if losses are much larger than wins.

---

## 30. Profit Factor

Profit factor compares total profits to total losses.

```math
ProfitFactor
=
\frac{\text{Gross Profit}}
{\left|\text{Gross Loss}\right|}
```

A profit factor greater than `1` means total profits exceeded total losses.

---

## 31. Turnover

Turnover measures how much the portfolio changes.

```math
Turnover_t
=
\sum_i
\left|
w_{i,t}^{new}
-
w_{i,t}^{old}
\right|
```

High turnover may indicate:

- more trading
- more transaction costs
- more tax consequences
- less stable portfolio behavior

---

## 32. Monte Carlo Testing

Monte Carlo testing runs many simulated versions of a strategy or market path.

If a strategy is tested over `N` simulations, then final value can be summarized as:

```math
\bar{V}_T
=
\frac{1}{N}
\sum_{s=1}^{N}
V_T^{(s)}
```

where `s` indexes the simulation.

Monte Carlo testing can help estimate:

- average outcome
- worst-case outcomes
- distribution of returns
- probability of loss
- probability of outperforming a benchmark
- sensitivity to randomness

Large Monte Carlo runs must be handled carefully because they can create excessive output files and disk usage.

---

## 33. Selection Bias Warning

A strategy can look better than it really is if the stock universe is hand-picked.

If the universe mostly contains stocks that performed well historically, or stocks chosen because they are personally interesting, the backtest may suffer from selection bias.

Future validation should include broader universes, such as:

- S&P 500 constituents
- Russell 1000
- Russell 3000
- sector-based universes
- random stock baskets
- historical index constituents where possible

The project should explicitly test whether results survive outside a personally selected stock list.

---

## 34. Lookahead Bias Warning

Lookahead bias happens when the strategy uses information that would not have been available at the time of the trade.

Every signal should be calculated only using information available at time `t`.

Correct structure:

```math
Signal_t \rightarrow Decision_t \rightarrow Return_{t+1}
```

Incorrect structure:

```math
Return_{t+1} \rightarrow Signal_t
```

The second structure leaks future information into the signal.

---

## 35. Project Direction

The long-term architecture is:

```math
Strategies
\rightarrow
Orthogonalization
\rightarrow
Allocator
\rightarrow
Risk
\rightarrow
Execution
```

The strategy engines generate signals.

The orthogonalization layer checks whether signals are truly different or just duplicates of the same idea.

The allocator decides how much capital each signal or asset should receive.

The risk layer controls exposure, drawdown, volatility, concentration, and cash.

The execution layer handles trades, transaction costs, slippage, and implementation details.

The current goal is to build enough strong engines so that the allocator eventually has meaningful signals to choose from.

---

## 36. Implementation Status

Some formulas in this document describe currently implemented behavior. Other formulas describe planned or research-direction behavior.

When expanding the system, each strategy or engine should eventually document:

- the exact formula used
- the lookback window
- the required input data
- the rebalance frequency
- the signal direction
- the risk controls
- known limitations
