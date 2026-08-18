# Phase 20: peer/spread contract tests

Phase 20 adds deterministic tests around the existing peer/spread
implementations without changing production code.

The tests preserve the three-path distinction:

- package-oriented Parquet/features path;
- staged cached peer-search plus spread-generation path;
- one-pass cached matrix path.

The staged generator keeps its historical `ticker_return` and `avg_peer_corr`
schema. The one-pass path keeps the canonical downstream names
`stock_return` and `top_k_avg_corr`; no implicit adapter is introduced.

The fixture uses ten deterministic tickers over 24 dates, including identical,
negative, weak, missing, zero-variance, and near-tie relationships. Golden
assertions cover peer selection, spread arithmetic, schemas, and ordering;
property assertions cover self-exclusion, bounds, finite values, and repeatable
execution. Exact platform-sensitive tie policy is not invented.

No network, large matrices, Parquet artifacts, Rust, or quantitative jobs are
used.
