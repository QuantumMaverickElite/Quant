# Phase 24: final implementation cleanup

Phase 24 completed the final planned major implementation-ownership extraction
before Reorg V1 turns to artifacts, root topology, preservation, and freeze
validation. No signal, portfolio, peer/spread, threshold, or Rust methodology
was changed.

## Mean-reversion daily evaluator

Reusable ownership now lives in
`src/backtester/backtests/mean_reversion_daily_portfolio.py`. It owns the
`OpenPosition` schema, order filtering/ranking and trading-date alignment,
mark-to-market behavior, overlapping-position simulation, fees, equity/trade
frames, and summary statistics. The stable script retains argparse, signal and
price loading, output paths and writes, progress, and presentation while
re-exporting the package helpers.

Contracts in `tests/test_mean_reversion_daily_portfolio_contracts.py` protect
the historical next-session entry, configured trading-session exit, long-only
confidence weighting, duplicate preservation, capped weights without
redistribution, exit-before-entry processing, missing-price mark behavior,
fee accounting, output schemas, metrics, and repeatability.

## Strategy scorecard decision

`scripts/strategy_scorecard.py` is `LEAVE_AS_COMMAND`. Its 1,110 lines form one
standalone research-reporting application: filesystem discovery, permissive
schema inference, equity construction, metric policy, benchmark comparison,
four score modes, terminal formatting, Markdown writing, and CLI behavior.
There are no tracked code callers. Similar metric names elsewhere use different
inputs and research semantics, so extraction would create an unproven shared
authority rather than remove established duplication.

## Implementation freeze disposition

- one-pass cached peer/spread: separate, contract-protected methodology;
  `SAFE_TO_DEFER`;
- threshold V2/V3 and matrix generations: unresolved authority;
  `RESEARCH` / `SAFE_TO_DEFER`;
- remaining MarketState scan, trade, and Monte Carlo commands: data-dependent
  research/compatibility; `RESEARCH`;
- historical intelligence stress and training launchers: reproducibility and
  orchestration commands; `HISTORICAL/COMPATIBILITY` or `LEGITIMATE_COMMAND`;
- matrix/returns/Rust exporters: compatibility-sensitive cross-language
  commands; `LEGITIMATE_COMMAND`.

No further major script extraction is required before Reorg V1 freeze. Future
changes to these families require their own authority or contract campaigns.
