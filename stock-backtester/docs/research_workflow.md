# Research workflow

Research should produce results that can be revisited, compared, and either
adopted or rejected without mixing experiment code into shared implementation.

## Lifecycle

```text
research question
  -> explicit baseline and hypothesis
  -> reusable implementation under src/ when appropriate
  -> experiment or evaluation under research/
  -> typed registry/config metadata where applicable
  -> ablation, control, and leakage checks
  -> predictable output with provenance
  -> documented result and decision about what to use next
```

## Where work belongs

- `src/backtester/`: reusable quantitative behavior and stable domain types.
- `scripts/`: stable commands, orchestration, compatibility wrappers, and
  command-heavy implementations awaiting extraction.
- `research/`: experiments, evaluations, ablations, diagnostics, and programs
  retained so older results can be reproduced.
- `tests/`: small deterministic contracts and regressions. Tests are not
  research executables and should not require live data.
- `tools/`: repository maintenance rather than market research.
- `outputs/`: generated results and caches; maintain code under `src/` or
  `research/`, not here.

## Experiment and configuration registry

Use `backtester.experiments` when an experiment or command benefits from typed,
discoverable metadata. The registry records purpose, subsystem, command paths,
inputs, outputs, and parameter semantics; it does not execute research or
promote results.

```bash
PYTHONPATH=src python -m backtester.experiments list
PYTHONPATH=src python -m backtester.experiments describe <id>
PYTHONPATH=src python -m backtester.experiments config <id>
PYTHONPATH=src python -m backtester.experiments validate
```

Do not define the same parameter differently in a CLI and the typed registry.

## Benchmark discipline

A credible result should identify:

- the research question and rejection criterion;
- baseline and control implementations;
- universe, period, horizon, and sampling method;
- feature availability time and leakage controls;
- seeds and deterministic tie behavior;
- input hashes, code commit, and dependency versions;
- output manifest and compact summaries;
- ablations and same-universe comparisons;
- whether the result is current, historical, fallback, rejected, or unresolved.

Do not choose a default from the newest filename, largest output, or best
in-sample score. Historical ML-policy results, threshold variants, and H20/H100
mean-reversion variants remain separate until the research supports a choice.

## From script to package

An experiment may begin as a self-contained research program. Extract behavior
under `src/` when it is reused, becomes a stable contract, or makes a command
wrapper materially thinner. Add deterministic contracts before moving
quantitative implementation. Preserve command paths and output schemas when
other workflows depend on them.

## Results and promotion

Write outputs beneath a predictable family and save a compact manifest. Keep
conclusions close to the research family README or a scoped result note. Moving
a file or registering metadata does not make an experiment the new baseline;
record that decision separately with the supporting comparison.

See [output policy](output_policy.md),
[reproducibility](reproducibility.md), and the
[research directory map](../research/README.md).
