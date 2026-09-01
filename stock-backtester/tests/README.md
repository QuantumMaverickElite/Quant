# Tests

`tests/` is for small, deterministic validation of repository and package
contracts. It is not a home for research executables, live-data checks, or
long-running experiments.

The current offline tests are:

- `test_table_io.py` — CSV/Parquet table contract checks.
- `test_ml_policy_family.py` — historical ML-policy compatibility/regression checks.
- `test_experiment_registry.py` — discovery registry integrity and JSON checks.
- `test_parameter_config_registry.py` — typed configuration validation checks.
- `test_reorg_phase0_inventory.py` — bounded inventory/overlay contract checks.
- `test_intelligence_training_orchestration.py` — manifest and child-command
  orchestration contracts.
- `test_peer_spread_contracts.py` — deterministic cached peer-search, staged
  spread, one-pass schema, and downstream signal contracts.
- `test_market_state_contracts.py` — deterministic MarketState composition,
  fast feature-row, rebalance, momentum, portfolio weighting/return, schema,
  and script-to-package compatibility contracts.
- `test_mean_reversion_daily_portfolio_contracts.py` — deterministic signal
  ordering, execution lag, duplicate handling, exposure sizing, fees,
  mark-to-market, trade/equity schemas, summary, and compatibility contracts.
- `test_dividend_capture_contracts.py` — standalone historical dividend
  calendar, schema, shifted-regime, profile, long/short, and long-only research
  behavior without downloads or output writes.

From `stock-backtester/`, run the current offline suite with:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_table_io tests.test_ml_policy_family \
  tests.test_experiment_registry tests.test_parameter_config_registry \
  tests.test_reorg_phase0_inventory \
  tests.test_intelligence_training_orchestration \
  tests.test_peer_spread_contracts tests.test_market_state_contracts \
  tests.test_mean_reversion_daily_portfolio_contracts \
  tests.test_dividend_capture_contracts
```

Run one test module by replacing the module name, for example:

```bash
PYTHONPATH=src python -m unittest tests.test_experiment_registry
```

Regression/contract tests check stable behavior or interfaces. Research
experiments belong under `scripts/` or a documented research area; they should
not be named as tests merely because they print a diagnostic table.
