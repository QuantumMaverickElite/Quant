# Large-Universe Allocator and Market Fabric Notes

## Summary

This research pass moved the mean-reversion system from a small curated universe into a broader cleaned market universe.

The cleaned large-universe result was promising: the active system beat same-universe equal-weight buy-and-hold on final equity and Sharpe-like score, but had worse max drawdown.

## Key conclusion

The main improvement came from scaling the correlation/mean-reversion system to a broader cleaned universe and applying the volatility/entropy context system.

The deformation / combined allocator layer did not materially improve the large-universe result yet.

## Trusted large-universe result

Combined allocator on clean 2,401-stock universe:

- Final equity: $36,167.69
- Growth multiple: 3.62x
- Max drawdown: -42.18%
- Win rate: 44.71%
- Sharpe-like: 0.7415
- Same-date percentile: 84.04%
- Random-date percentile: 74.66%

Same-universe equal-weight buy-and-hold:

- Final equity: $24,775.45
- Growth multiple: 2.48x
- Max drawdown: -39.59%
- Sharpe-like: 0.6739

## Baseline versus combined allocator

Context-adjusted baseline:

- Final equity: $36,130.50
- Growth multiple: 3.61x
- Max drawdown: -42.18%
- Win rate: 45.09%
- Sharpe-like: 0.7424
- Random-date percentile: 74.82%

Combined allocator:

- Final equity: $36,167.69
- Growth multiple: 3.62x
- Max drawdown: -42.18%
- Win rate: 44.71%
- Sharpe-like: 0.7415
- Random-date percentile: 74.66%

Interpretation: deformation did not materially improve the large-universe result yet. The broad mean-reversion/correlation system plus volatility/entropy context is what mattered most.

## Market fabric visualization

A storage-conscious multi-frame market fabric was built:

- Frames: 88
- Period: 2019-03-29 to 2026-05-13
- Nodes per frame: 1,200
- Edges per frame: 4,000

The visual now supports cyan edges, allocator overlay, trade overlay, active-trade PnL coloring, portfolio HUD, cluster label JSON, ticker labels, and broader market background nodes.

The goal is to show not only what the strategy bought, but also the broader market field it chose from.

## Current visual command

    python visuals/visualize_market_graph_fabric.py \
      --frames-dir outputs/market_graph_fabric_frames/combined_clean_finaldate_2019_2026_step_30_with_trades \
      --visual-preset clean-points \
      --use-allocator-overlay \
      --allocator-highlight-top \
      --allocator-size-boost 5.0 \
      --use-trade-overlay \
      --ticker-labels \
      --cluster-labels \
      --cluster-label-map outputs/market_graph_fabric_frames/combined_clean_finaldate_2019_2026_step_30_with_trades/cluster_labels.json \
      --node-size 2.8 \
      --edge-alpha 0.14 \
      --edge-width 0.08 \
      --edge-cyan \
      --node-size-metric none

## Next steps

1. Improve cluster labels from actual frame node membership.
2. Add candidate-vs-selected visual distinction.
3. Test H=20 versus H=100 on the clean universe.
4. Test top-3 versus top-5 versus top-10.
5. Add an options overlay label engine.
6. Map signal horizon to option expiration.
7. Build short-signal evaluation, but do not trade shorts until filters are validated.
8. Rebuild ticker-level deformation sensitivity on the broad clean universe.
9. Keep benchmark discipline: strategy, same-universe buy-and-hold, and Monte Carlo controls.
10. Keep output storage compact by default.
