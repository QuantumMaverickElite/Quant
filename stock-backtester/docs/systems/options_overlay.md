# Options Overlay

The options overlay is a simplified experimental system.

It is not a production options model.

## Purpose

The overlay tests whether simplified straddle/strangle-style returns can improve or hurt a base equity strategy under certain regimes or tickers.

## Conditional Overlay

The overlay should not always be applied globally.

In testing, it helped some high-volatility names such as NVDA and TSLA, but dragged or did not help steadier names.

A ticker-gated overlay can be run like this:

```bash
for ticker in SPY QQQ AAPL MSFT NVDA TSLA; do
  python -m backtester.cli \
    --strategy regime \
    --ticker "$ticker" \
    --start 2015-01-01 \
    --end 2024-12-31 \
    --use-regime-router \
    --use-options-overlay \
    --options-overlay-tickers NVDA TSLA \
    --output-root outputs/experiments/conditional_options_overlay
done
```

Expected behavior:

```text
SPY, QQQ, AAPL, MSFT -> options overlay skipped
NVDA, TSLA           -> options overlay active
```

## Evaluation

```bash
python scripts/strategy_scorecard.py outputs/experiments/conditional_options_overlay/regime \
  --equity-column combined_equity \
  --latest-only

python scripts/compare_equity_layers.py outputs/experiments/conditional_options_overlay/regime \
  --latest-only
```

## Limitations

The current options overlay is simplified. It does not fully model realistic options chains, Greeks, liquidity, assignment, implied volatility surface behavior, or transaction costs.
