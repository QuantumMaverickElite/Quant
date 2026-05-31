# Strategy Math and Signal Definitions

This document explains the mathematical ideas used across the backtesting system.

The goal is not only to document what each strategy does, but also to make the logic understandable to someone reading the project without needing to reverse-engineer the code.

The project is built around several layers:

1. Price and return calculations
2. Strategy signals
3. Volatility and regime engines
4. Scoring and ranking
5. Allocation
6. Risk controls
7. Backtest evaluation metrics

---

# 1. Price and Return Math

Let:

- \(P\_{i,t}\) be the price of asset \(i\) at time \(t\)
- \(r\_{i,t}\) be the simple return of asset \(i\) at time \(t\)
- \(\ell\_{i,t}\) be the log return of asset \(i\) at time \(t\)

Simple return:

\[
r*{i,t} = \frac{P*{i,t}}{P\_{i,t-1}} - 1
\]

Log return:

\[
\ell*{i,t} = \log(P*{i,t}) - \log(P\_{i,t-1})
\]

Portfolio return:

\[
r*{p,t} = \sum*{i=1}^{N} w*{i,t} r*{i,t}
\]

where:

- \(w\_{i,t}\) is the portfolio weight assigned to asset \(i\)
- \(N\) is the number of assets in the universe

Portfolio value:

\[
V*t = V*{t-1}(1 + r\_{p,t})
\]

---

# 2. Momentum Signals

A momentum signal measures whether an asset has recently been rising or falling.

For a lookback window \(k\), the momentum of asset \(i\) is:

\[
M*{i,t}^{(k)} = \frac{P*{i,t}}{P\_{i,t-k}} - 1
\]

A positive value means the asset has gone up over the lookback period.

A negative value means the asset has gone down over the lookback period.

A basic momentum strategy may rank assets by \(M\_{i,t}^{(k)}\) and buy the strongest assets.

---

# 3. Mean Reversion Signals

A mean reversion signal measures how far an asset is from its recent average.

Rolling mean:

\[
\mu*{i,t}^{(k)} = \frac{1}{k}\sum*{j=0}^{k-1} P\_{i,t-j}
\]

Rolling standard deviation:

\[
\sigma*{i,t}^{(k)} = \sqrt{\frac{1}{k-1}\sum*{j=0}^{k-1}(P*{i,t-j} - \mu*{i,t}^{(k)})^2}
\]

Z-score:

\[
z*{i,t}^{(k)} = \frac{P*{i,t} - \mu*{i,t}^{(k)}}{\sigma*{i,t}^{(k)}}
\]

Interpretation:

- \(z\_{i,t} > 0\): price is above its recent average
- \(z\_{i,t} < 0\): price is below its recent average
- very negative \(z\): possible oversold condition
- very positive \(z\): possible overbought condition

A simple mean reversion strategy may buy assets with low z-scores and avoid or reduce exposure to assets with high z-scores.

---

# 4. Volatility Signals

Volatility measures how much an asset moves.

Using returns over a lookback window \(k\), rolling volatility is:

\[
\sigma*{i,t}^{(k)} = \sqrt{\frac{1}{k-1}\sum*{j=0}^{k-1}(r*{i,t-j} - \bar{r}*{i,t}^{(k)})^2}
\]

Annualized volatility:

\[
\sigma*{i,t,\text{ann}}^{(k)} = \sqrt{252} \cdot \sigma*{i,t}^{(k)}
\]

where 252 is the approximate number of trading days in a year.

Volatility can be used in several ways:

1. As a risk penalty
2. As a regime signal
3. As a position sizing input
4. As a trigger for reducing exposure
5. As a high-volatility opportunity signal

---

# 5. GARCH Volatility Engine

The GARCH engine estimates changing volatility over time.

A common model is GARCH(1,1):

\[
r_t = \mu + \epsilon_t
\]

\[
\epsilon_t = \sigma_t z_t
\]

\[
\sigma*t^2 = \omega + \alpha \epsilon*{t-1}^2 + \beta \sigma\_{t-1}^2
\]

where:

- \(\sigma_t^2\) is the conditional variance at time \(t\)
- \(\omega\) is the baseline variance level
- \(\alpha\) controls how strongly recent shocks affect volatility
- \(\beta\) controls how persistent volatility is
- \(\epsilon\_{t-1}^2\) is the previous squared shock
- \(z_t\) is usually assumed to be a standardized random variable

Interpretation:

- A large shock increases future volatility.
- A high \(\beta\) means volatility decays slowly.
- GARCH is useful because market volatility clusters. Large moves tend to be followed by large moves, and calm periods tend to be followed by calm periods.

The GARCH engine can be used to estimate future risk and help decide whether the system should increase, reduce, or reroute exposure.

---

# 6. Entropy Engine

Entropy measures disorder, uncertainty, or unpredictability.

For a set of possible market states with probabilities \(p_1, p_2, \dots, p_n\), Shannon entropy is:

\[
H = -\sum\_{i=1}^{n} p_i \log(p_i)
\]

Interpretation:

- Low entropy means the system is more ordered or predictable.
- High entropy means the system is more uncertain or chaotic.

In a market setting, entropy can be estimated from return distributions, regime probabilities, signal distributions, or transition behavior.

Example using binned return states:

\[
H*t = -\sum*{j=1}^{m} p*{j,t} \log(p*{j,t})
\]

where:

- \(p\_{j,t}\) is the probability of returns falling into bin \(j\)
- \(m\) is the number of bins

The entropy engine can help detect whether the market is in a clean directional environment or a noisy unstable environment.

Possible interpretation:

- Low entropy + positive trend: cleaner momentum environment
- High entropy + high volatility: unstable risk environment
- Low entropy + compressed volatility: possible pre-breakout environment

---

# 7. Regime Engine

A regime engine classifies the market into different states.

Examples:

- bull regime
- bear regime
- sideways regime
- high-volatility regime
- low-volatility regime
- crisis regime
- recovery regime

A simple regime score may combine trend and volatility:

\[
R_t = a \cdot T_t - b \cdot \sigma_t
\]

where:

- \(T_t\) is a trend signal
- \(\sigma_t\) is volatility
- \(a\) and \(b\) are weights

A simple trend signal could be:

\[
T_t = \frac{P_t}{MA_t^{(k)}} - 1
\]

where \(MA_t^{(k)}\) is a moving average.

Possible regime classification:

\[
\text{Regime}_t =
\begin{cases}
\text{Bull}, & T_t > 0 \text{ and } \sigma_t < \sigma_{\text{high}} \\
\text{Volatile Bull}, & T*t > 0 \text{ and } \sigma_t \geq \sigma*{\text{high}} \\
\text{Bear}, & T*t < 0 \text{ and } \sigma_t < \sigma*{\text{high}} \\
\text{Crisis}, & T*t < 0 \text{ and } \sigma_t \geq \sigma*{\text{high}}
\end{cases}
\]

The regime engine allows the strategy to behave differently depending on market conditions.

For example:

- In a bull regime, the system may allow higher equity exposure.
- In a bear regime, the system may reduce exposure.
- In a crisis regime, the system may use stricter risk controls.
- In a sideways regime, the system may favor mean reversion instead of momentum.

---

# 8. Correlation Engine

The correlation engine measures how similarly assets move.

For assets \(i\) and \(j\), rolling correlation is:

\[
\rho\_{ij,t}^{(k)} =
\frac{\text{Cov}(r_i, r_j)}
{\sigma_i \sigma_j}
\]

where:

- \(\rho\_{ij,t}^{(k)}\) is the rolling correlation between assets \(i\) and \(j\)
- \(\text{Cov}(r_i, r_j)\) is the covariance of their returns
- \(\sigma_i\) and \(\sigma_j\) are their volatilities

Interpretation:

- \(\rho \approx 1\): assets move together
- \(\rho \approx 0\): assets are mostly unrelated
- \(\rho \approx -1\): assets move in opposite directions

The correlation engine can help avoid building a portfolio that appears diversified but is actually concentrated in similar assets.

Average portfolio correlation:

\[
\bar{\rho}_t =
\frac{2}{N(N-1)}
\sum_{i<j} \rho\_{ij,t}
\]

A high average correlation may indicate that diversification is weakening.

---

# 9. High-Volatility Engine

The high-volatility engine looks for situations where volatility itself may create opportunity.

A high-volatility score may be based on how current volatility compares to recent volatility.

Volatility z-score:

\[
z*{\sigma,t} =
\frac{\sigma_t - \mu*{\sigma,t}^{(k)}}{\sigma\_{\sigma,t}^{(k)}}
\]

where:

- \(\sigma_t\) is current volatility
- \(\mu\_{\sigma,t}^{(k)}\) is average volatility over a lookback window
- \(\sigma\_{\sigma,t}^{(k)}\) is the standard deviation of volatility over that window

Interpretation:

- high \(z\_{\sigma,t}\): volatility is unusually high
- low \(z\_{\sigma,t}\): volatility is unusually low

The high-volatility engine can be used in two different ways:

1. Defensive mode: reduce exposure during abnormal volatility
2. Opportunity mode: look for oversold assets after volatility spikes

For example, a high-volatility mean-reversion setup may require:

\[
z\_{\sigma,t} > c
\]

and

\[
z\_{price,t} < -d
\]

This means volatility is unusually high and price is unusually low.

---

# 10. Volatility Router

A volatility router changes the behavior of the strategy depending on volatility conditions.

Example:

\[
\text{Route}_t =
\begin{cases}
\text{Normal Strategy}, & \sigma_t < \sigma_{\text{medium}} \\
\text{Reduced Exposure}, & \sigma*{\text{medium}} \leq \sigma_t < \sigma*{\text{high}} \\
\text{Extreme Risk Mode}, & \sigma*t \geq \sigma*{\text{high}}
\end{cases}
\]

The router does not necessarily create a signal by itself. Instead, it decides which strategy behavior should be active.

For example:

- Low volatility: allow normal allocation
- Medium volatility: reduce position sizes
- High volatility: use defensive rules
- Extreme volatility: only trade if the opportunity is very strong

---

# 11. Dividend Signal

A dividend signal can rank assets based on dividend-related events or yield.

Dividend yield:

\[
DY*{i,t} = \frac{D*{i,t}}{P\_{i,t}}
\]

where:

- \(D\_{i,t}\) is annual dividend per share
- \(P\_{i,t}\) is price

A dividend capture strategy may focus on the ex-dividend date.

A simplified event return around a dividend date can be written as:

\[
R*{event} = \frac{P*{sell} + D - P*{buy}}{P*{buy}}
\]

where:

- \(P\_{buy}\) is the entry price
- \(P\_{sell}\) is the exit price
- \(D\) is the dividend received

This type of signal is event-driven rather than purely technical.

---

# 12. Buyback Signal

A buyback signal attempts to capture the effect of companies repurchasing their own shares.

A simple buyback yield can be estimated as:

\[
BY*{i,t} = \frac{\text{Net Buybacks}*{i,t}}{\text{Market Cap}\_{i,t}}
\]

Buybacks can matter because reducing the share count may increase ownership concentration and earnings per share.

The signal may become stronger when buybacks are large relative to market capitalization.

---

# 13. Stock Split Signal

A stock split signal is event-driven.

For a split ratio \(a:b\), the adjusted price is:

\[
P*{\text{after}} = P*{\text{before}} \cdot \frac{b}{a}
\]

The market value of the position does not mechanically change from the split itself.

However, splits may affect:

- liquidity
- retail accessibility
- market attention
- post-event momentum

A split signal should therefore be treated as an event signal, not as guaranteed alpha.

---

# 14. Options Layer

The options layer is conditional.

It should not always be active. Instead, it should depend on the state of the underlying asset, volatility, and the strategy signal.

A simplified options decision rule may look like:

\[
O_t =
\begin{cases}
1, & \text{signal strength} > c \text{ and volatility condition is favorable} \\
0, & \text{otherwise}
\end{cases}
\]

where \(O_t = 1\) means the options layer is allowed.

The options layer can be used to express stronger conviction, hedge risk, or create asymmetric exposure.

Because options introduce nonlinear payoff behavior, they should be treated separately from ordinary equity exposure.

---

# 15. Signal Normalization

Different signals may have different scales.

For example:

- momentum may be measured in percent return
- volatility may be measured as standard deviation
- entropy may be measured using probabilities
- correlation may range from -1 to 1

To combine signals, they should often be normalized.

Z-score normalization:

\[
x*{i,t}^{norm} =
\frac{x*{i,t} - \mu_t(x)}
{\sigma_t(x)}
\]

Rank normalization:

\[
x*{i,t}^{rank} =
\frac{\text{rank}(x*{i,t})}{N}
\]

Normalization allows different signals to be combined into one score more safely.

---

# 16. Composite Scoring Model

A composite score combines multiple signals.

Example:

\[
S*{i,t}
=
\alpha_1 M*{i,t}

- \alpha*2 MR*{i,t}
- \alpha*3 D*{i,t}
- \alpha*4 B*{i,t}

* \alpha*5 \sigma*{i,t}
* \alpha*6 C*{i,t}
  \]

where:

- \(S\_{i,t}\) is the total score for asset \(i\)
- \(M\_{i,t}\) is momentum
- \(MR\_{i,t}\) is mean reversion
- \(D\_{i,t}\) is dividend score
- \(B\_{i,t}\) is buyback score
- \(\sigma\_{i,t}\) is volatility
- \(C\_{i,t}\) is concentration or correlation penalty
- \(\alpha_j\) are signal weights

The scoring model is important because the long-term goal of the project is not only to test isolated strategies, but to build a system that can compare and rotate between opportunities.

---

# 17. Top-K Selection

A simple allocator may select the top \(k\) assets by score.

\[
\text{Selected}_t = \text{TopK}(S_{i,t})
\]

Equal-weight allocation:

\[
w\_{i,t} =
\begin{cases}
\frac{1}{k}, & i \in \text{Selected}\_t \\
0, & \text{otherwise}
\end{cases}
\]

This is simple and interpretable, but it may ignore differences in conviction, volatility, and correlation.

---

# 18. Score-Weighted Allocation

A score-weighted allocator assigns more capital to higher-scoring assets.

\[
w*{i,t} =
\frac{\max(S*{i,t}, 0)}
{\sum*{j=1}^{N} \max(S*{j,t}, 0)}
\]

This only gives weight to assets with positive scores.

A more conservative version may apply a maximum position size:

\[
w*{i,t} \leq w*{\max}
\]

---

# 19. Volatility-Adjusted Allocation

A volatility-adjusted allocator gives less weight to more volatile assets.

One simple version:

\[
\tilde{w}_{i,t} =
\frac{S_{i,t}}{\sigma\_{i,t}}
\]

Then normalize:

\[
w*{i,t} =
\frac{\max(\tilde{w}*{i,t}, 0)}
{\sum*{j=1}^{N} \max(\tilde{w}*{j,t}, 0)}
\]

This rewards high score but penalizes high risk.

---

# 20. Correlation-Aware Allocation

A correlation-aware allocator reduces concentration in highly correlated assets.

One possible penalty:

\[
Penalty*{i,t} =
\frac{1}{k}
\sum*{j \in Portfolio} \rho\_{ij,t}
\]

Adjusted score:

\[
S*{i,t}^{adj} = S*{i,t} - \lambda Penalty\_{i,t}
\]

where:

- \(\lambda\) controls how strongly correlation is penalized
- higher penalty means the asset is too similar to existing holdings

This helps prevent the portfolio from accidentally becoming concentrated in one theme, sector, or risk factor.

---

# 21. Threshold Rebalancing

Threshold rebalancing avoids trading unless portfolio weights drift far enough from target weights.

Let:

- \(w\_{i,t}^{actual}\) be the current actual weight
- \(w\_{i,t}^{target}\) be the desired target weight
- \(\theta\) be the rebalance threshold

Rebalance condition:

\[
|w*{i,t}^{actual} - w*{i,t}^{target}| > \theta
\]

If the difference is smaller than the threshold, the portfolio does not trade.

This can reduce turnover, transaction costs, and unnecessary trading.

---

# 22. Risk Scaling

Risk scaling changes total exposure based on market conditions.

Example:

\[
E_t =
\begin{cases}
1.00, & \text{low risk} \\
0.75, & \text{medium risk} \\
0.50, & \text{high risk} \\
0.25, & \text{extreme risk}
\end{cases}
\]

Final weight:

\[
w*{i,t}^{final} = E_t \cdot w*{i,t}^{target}
\]

Cash weight:

\[
w*{cash,t} = 1 - \sum_i w*{i,t}^{final}
\]

Risk scaling allows the system to stay invested during favorable conditions and reduce exposure during dangerous conditions.

---

# 23. Transaction Costs

Transaction costs reduce portfolio value when trades occur.

If turnover at time \(t\) is:

\[
TO*t = \sum_i |w*{i,t}^{new} - w\_{i,t}^{old}|
\]

and the transaction cost rate is \(c\), then cost is:

\[
Cost_t = c \cdot TO_t \cdot V_t
\]

Portfolio value after costs:

\[
V_t^{after} = V_t^{before} - Cost_t
\]

Transaction costs are important because a strategy can look good before costs but fail after realistic trading friction.

---

# 24. Slippage

Slippage measures the difference between expected execution price and actual execution price.

For a buy order:

\[
Slippage = \frac{P*{actual} - P*{expected}}{P\_{expected}}
\]

For a sell order:

\[
Slippage = \frac{P*{expected} - P*{actual}}{P\_{expected}}
\]

Slippage is especially important for:

- small-cap stocks
- high-volatility stocks
- large orders
- low-liquidity assets
- fast-moving markets

---

# 25. CAGR

Compound annual growth rate measures annualized return.

\[
CAGR =
\left(
\frac{V_T}{V_0}
\right)^{1/Y}

- 1
  \]

where:

- \(V_T\) is final portfolio value
- \(V_0\) is starting portfolio value
- \(Y\) is the number of years

---

# 26. Volatility of Portfolio Returns

Daily portfolio volatility:

\[
\sigma*p = std(r*{p,t})
\]

Annualized portfolio volatility:

\[
\sigma\_{p,ann} = \sqrt{252} \cdot \sigma_p
\]

---

# 27. Sharpe Ratio

Sharpe ratio measures return per unit of volatility.

\[
Sharpe =
\frac{\mathbb{E}[r_p - r_f]}{\sigma_p}
\]

Annualized Sharpe using daily returns:

\[
Sharpe\_{ann} =
\frac{\bar{r}\_p - \bar{r}\_f}
{\sigma_p}
\sqrt{252}
\]

where:

- \(r_p\) is portfolio return
- \(r_f\) is risk-free return
- \(\sigma_p\) is volatility of portfolio returns

---

# 28. Maximum Drawdown

Drawdown measures decline from a previous peak.

Running peak:

\[
Peak*t = \max*{\tau \leq t} V\_{\tau}
\]

Drawdown:

\[
DD_t =
\frac{V_t - Peak_t}{Peak_t}
\]

Maximum drawdown:

\[
MDD = \min_t DD_t
\]

Maximum drawdown is one of the most important risk metrics because it shows the worst peak-to-trough loss.

---

# 29. Win Rate

Win rate measures the percentage of profitable trades.

\[
WinRate =
\frac{\text{Number of Winning Trades}}
{\text{Total Number of Trades}}
\]

Win rate alone is not enough. A strategy can have a high win rate and still lose money if losses are much larger than wins.

---

# 30. Profit Factor

Profit factor compares total profits to total losses.

\[
ProfitFactor =
\frac{\text{Gross Profit}}
{|\text{Gross Loss}|}
\]

A profit factor greater than 1 means total profits exceeded total losses.

---

# 31. Turnover

Turnover measures how much the portfolio changes.

\[
Turnover*t =
\sum_i |w*{i,t}^{new} - w\_{i,t}^{old}|
\]

High turnover may indicate:

- more trading
- more transaction costs
- more tax consequences
- less stable portfolio behavior

---

# 32. Monte Carlo Testing

Monte Carlo testing runs many simulated versions of a strategy or market path.

If a strategy is tested over \(N\) simulations, then a metric such as final value can be summarized as:

\[
\bar{V}_T =
\frac{1}{N}
\sum_{s=1}^{N} V\_{T}^{(s)}
\]

where \(s\) indexes the simulation.

Monte Carlo testing can help estimate:

- average outcome
- worst-case outcomes
- distribution of returns
- probability of loss
- probability of outperforming a benchmark
- sensitivity to randomness

However, Monte Carlo outputs must be managed carefully because large simulations can create excessive files and disk usage.

---

# 33. Selection Bias Warning

A strategy can look better than it really is if the stock universe is hand-picked.

If the universe mostly contains stocks that performed well historically or stocks chosen because they are personally interesting, the backtest may suffer from selection bias.

Future validation should include broader universes, such as:

- S&P 500 constituents
- Russell 1000
- Russell 3000
- sector-based universes
- random stock baskets
- historical index constituents where possible

The project should explicitly test whether results survive outside a personally selected stock list.

---

# 34. Lookahead Bias Warning

Lookahead bias happens when the strategy uses information that would not have been available at the time of the trade.

For example, using future earnings, future index membership, future fundamentals, or future price behavior to make a past decision creates invalid results.

Every signal should be calculated only using information available at time \(t\).

The correct structure is:

\[
Signal*t \rightarrow Decision_t \rightarrow Return*{t+1}
\]

not:

\[
Return\_{t+1} \rightarrow Signal_t
\]

---

# 35. Project Direction

The long-term architecture is:

\[
Strategies
\rightarrow
Orthogonalization
\rightarrow
Allocator
\rightarrow
Risk
\rightarrow
Execution
\]

The strategy engines generate signals.

The orthogonalization layer checks whether signals are truly different or just duplicates of the same idea.

The allocator decides how much capital each signal or asset should receive.

The risk layer controls exposure, drawdown, volatility, concentration, and cash.

The execution layer handles trades, transaction costs, slippage, and implementation details.

The current goal is to build enough strong engines so that the allocator eventually has meaningful signals to choose from.
