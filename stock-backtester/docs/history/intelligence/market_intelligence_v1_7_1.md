# Market Intelligence v1.7.1

Hotfix for missing intelligence coverage.

## Fix

Rows on the latest signal date that were not part of the intelligence sweep are now labeled:

```text
intelligence_missing_not_evaluated
```

They are no longer mislabeled as:

```text
same_regime_scale_in_allowed
```

By default, missing intelligence rows keep position scale `1.0`. They are not penalized, but they are no longer counted as clean.
