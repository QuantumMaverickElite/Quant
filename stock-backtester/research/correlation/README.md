# Correlation and deformation research

This directory owns research questions about how correlation regime and
deformation features change signal and portfolio behavior:

- deformation evaluation across horizons;
- subperiod and yearly comparisons;
- changed-order comparisons between baseline and weighted signals;
- correlation/regime feature inspection;
- diagnostic plots.

The moved programs are research diagnostics, not automated tests. Reusable
correlation implementation remains under `src/backtester/correlation/`, and
stable pipeline commands remain under `scripts/`.

Mean-reversion construction remains under `src/backtester/signals/`; these
experiments live here because their research question is deformation.
H20/H100 defaults remain experiment configuration, not authority.
