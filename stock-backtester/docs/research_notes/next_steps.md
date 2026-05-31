# Next Steps

Near-term priorities:

```text
1. Keep output storage under control.
2. Preserve important baselines as compressed artifacts.
3. Expand matrix batch ops into reusable allocator primitives.
4. Add multi-signal matrix support.
5. Add correlation and risk matrix operations.
6. Add experiment manifests for reproducibility.
7. Audit lookahead bias and selection bias.
8. Test broader, less hand-picked universes.
9. Build a stronger allocator that combines many signals.
10. Use GPU only where matrix scale justifies it.
```

## Immediate Next Technical Work

Useful next modules:

```text
multi-signal matrix combination
rolling correlation and covariance
portfolio risk diagnostics
experiment manifest writer
lookahead audit script
universe construction tools
```

## Strategic Direction

The allocator should become a system that combines:

```text
signals
risk
correlation
regime state
constraints
portfolio-level exposure
```

It should not be hardcoded around one top-N signal.

## Storage Direction

Do not save large outputs by default.

Use:

```text
--save-mode none
--save-mode compact
--save-mode plots
--save-mode full only when needed
```

Important baselines should be compressed and stored externally.
