# Reproducibility

Reproducibility is part of the research system.

A backtest result is not trustworthy if it changes silently because of dependency versions, hidden tie behavior, data changes, or untracked experiment settings.

## Deterministic Allocator Selection

A previous allocator selection path used:

```python
np.argpartition(...)
np.argsort(...)
```

This was fast, but unstable when scores tied. Different NumPy versions could choose tied candidates differently.

This mattered especially for low-threshold rebalance tests, because threshold `0.00` rebalanced constantly. Small ordering differences compounded into material equity-curve differences.

The fixed rule is:

```text
1. Higher score wins.
2. If scores tie, lower ticker column index wins.
```

This makes the allocator deterministic across NumPy versions.

## What Should Be Recorded

Future experiments should save a small manifest with:

```text
code commit hash
dependency versions
input file paths
input file hashes
seed
sampled ticker universes
strategy parameters
save mode
created timestamp
```

This is much smaller than saving every curve, but it protects the experiment from becoming impossible to reproduce.

## Suggested Manifest Fields

```text
experiment_name
script_name
git_commit
python_version
numpy_version
pandas_version
scipy_version
cupy_version if used
feature_path
price_path
feature_hash
price_hash
runs
sample_size
portfolio_size
thresholds
rebalance_frequency
seed
save_mode
```

## Current Lesson

The project already found one real reproducibility bug: top-N selection was version-sensitive.

That bug was fixed by replacing unstable selection with deterministic tie-breaking.

Going forward, every allocator component should be audited for hidden nondeterminism.
