# Combined-signal research

This family compares allocator and signal behavior across baseline, heuristic
intelligence, ML intelligence, ranking, and related adjustment layers. It is
research analysis, not reusable implementation or allocator authority.

Signal construction
-------------------

- `build_allocator_intelligence_signals.py` — builds allocator-ready signals
  with intelligence-adjusted confidence.
- `build_allocator_intelligence_signals_v2.py` — adds the later opportunity/
  risk-scoring and event-feature options.

Comparison and diagnostics
--------------------------

- `compare_allocator_intelligence.py` — compares pre/post intelligence
  top-N allocator results.
- `compare_allocator_rankings.py` — compares arbitrary ranking columns across
  return horizons and portfolio sizes.
- `diagnose_allocator_intelligence.py` — writes a focused pre/post allocator
  diagnostic report.

Monte Carlo and strategy grids
------------------------------

- `monte_carlo_allocator_intelligence.py` — tests allocator-intelligence
  robustness for one ranking/top-N configuration.
- `monte_carlo_strategy_grid.py` — compares baseline volatility/entropy/
  correlation/mean-reversion ranking with the NLP-adjusted ranking across a
  top-N and return-horizon grid.

The v1/v2 builders are separate research generations; v2 is the later variant,
but repository-wide authority between them has not been formally declared.
The Monte Carlo scripts answer different questions and are intentionally not
merged.

Future combined-signal ablations may join this directory after their output and
command contracts are verified.
