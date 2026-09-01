# Research workflow

Research should produce evidence that can be revisited, compared, and either
promoted or rejected without confusing experiments with reusable authority.

## Lifecycle

```text
research question
  -> explicit baseline and hypothesis
  -> reusable implementation under src/ when appropriate
  -> experiment or evaluation under research/
  -> typed registry/config metadata where applicable
  -> ablation, control, and leakage checks
  -> predictable output with provenance
  -> documented result and authority decision
```

## Where work belongs

- `src/backtester/`: reusable quantitative behavior and stable domain types.
- `scripts/`: stable commands, orchestration, compatibility wrappers, and
  command-heavy implementations awaiting extraction.
- `research/`: experiments, evaluations, ablations, diagnostics, and historical
  reproducibility runners.
- `tests/`: small deterministic contracts and regressions. Tests are not
  research executables and should not require live data.
- `tools/`: repository maintenance rather than market research.
- `outputs/`: generated evidence and caches, never source-code authority.

## Experiment and configuration registry

Use `backtester.experiments` when an experiment or command benefits from typed,
discoverable metadata. The registry records purpose, ownership, command paths,
inputs, outputs, and parameter semantics; it does not execute research or
promote results.

```bash
PYTHONPATH=src python -m backtester.experiments list
PYTHONPATH=src python -m backtester.experiments describe <id>
PYTHONPATH=src python -m backtester.experiments config <id>
PYTHONPATH=src python -m backtester.experiments validate
```

Do not create parallel configuration semantics when an existing CLI or typed
registry representation already owns the parameter.

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

Do not infer authority from the newest filename, largest output, or best
in-sample score. Historical ML-policy results, threshold variants, and H20/H100
mean-reversion variants remain separate until an explicit decision is recorded.

## From script to package

An experiment may begin as a self-contained research program. Extract behavior
under `src/` when it is reused, becomes a stable contract, or makes a command
wrapper materially thinner. Add deterministic contracts before moving
quantitative implementation. Preserve command paths and output schemas when
they are compatibility interfaces.

## Results and promotion

Write outputs beneath a predictable family and save a compact manifest. Keep
research conclusions close to the research family README or a scoped result
note. Promotion requires explicit evidence and an authority decision; moving a
file or registering metadata is not promotion.

See [output policy](output_policy.md),
[reproducibility](reproducibility.md), and the
[research directory map](../research/README.md).
