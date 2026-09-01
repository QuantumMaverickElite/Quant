# Stock Backtester

Stock Backtester is the main quantitative research system in this repository.
It supports reusable analytics and backtest components, command-line research
pipelines, large-universe matrix workflows, intelligence/event-learning
research, portfolio evaluation, and Rust-accelerated stress testing.

This is a research system, not a claim that every strategy or implementation is
production-authoritative. Unresolved alternatives are documented as unresolved.

## Ten-minute map

| Question | Answer |
| --- | --- |
| Reusable implementation | [`src/backtester/`](src/backtester/) |
| Stable commands and compatibility wrappers | [`scripts/`](scripts/README.md) |
| Research experiments and evaluations | [`research/`](research/README.md) |
| Offline deterministic validation | [`tests/`](tests/README.md) |
| Repository maintenance tools | [`tools/reorg/`](tools/reorg/README.md) |
| Policies and registry configuration | [`configs/`](configs/README.md) |
| Generated and cached artifacts | `outputs/`; see [output policy](docs/output_policy.md) |
| Current architecture | [`docs/architecture.md`](docs/architecture.md) |
| Documentation authority map | [`docs/README.md`](docs/README.md) |
| Historical reorganization evidence | [`docs/reorg/`](docs/reorg/README.md) |
| Historical intelligence generations | [`docs/history/intelligence/`](docs/history/intelligence/README.md) |

## Environment

From `stock-backtester/`:

```bash
source .venv/bin/activate
export PYTHONPATH=src
export PYTHONDONTWRITEBYTECODE=1
```

Install the package only when the environment needs it:

```bash
python -m pip install -e .
```

Discover the registered research surface without running an experiment:

```bash
python -m backtester.experiments list
python -m backtester.experiments validate
```

## Main systems

- **Large-universe mean reversion:** universe and matrix preparation, peer
  search, peer-basket spreads, signals, market context, optional deformation,
  portfolio evaluation, and Rust stress interfaces. Start with the
  [large-universe runbook](docs/large_universe_pipeline.md).
- **Market state and allocators:** volatility, entropy, routing, matrix
  allocator, and threshold-rebalance research. Start with
  [system documentation](docs/systems/) and
  [engine ownership](src/backtester/engines/README.md).
- **Correlation and deformation:** reusable implementation is under
  [`src/backtester/correlation/`](src/backtester/correlation/README.md);
  evaluations and diagnostics are under
  [`research/correlation/`](research/correlation/README.md).
- **Intelligence and event learning:** current event-learning research,
  operational heuristic fallback, and historical ML-policy research coexist
  but are not equivalent. Start with the
  [intelligence README](src/backtester/intelligence/README.md).
- **Rust stress engine:** Python prepares contracts and orchestrates work; Rust
  performs repeated stress computation. See
  [`rust_engine/README.md`](rust_engine/README.md).

## Research and validation

New research should follow the
[research workflow](docs/research_workflow.md): put reusable implementation
under `src/` when appropriate, experiment programs under `research/`, stable
commands under `scripts/`, and deterministic contracts under `tests/`.

Run the offline suite:

```bash
python -m unittest discover -s tests
python -m backtester.experiments validate
```

Some tests require NumPy/Pandas or other optional research dependencies and
skip cleanly in minimal environments. Live-data and synthetic smoke commands
remaining under `scripts/` are not interchangeable with offline tests.

## Outputs and history

Generated artifacts are intentionally not source authority. `outputs/`
contains a mixture of caches, matrices, training runs, research evidence,
reports, and temporary results; retention authority remains incomplete. Read
[the output policy](docs/output_policy.md) before cleaning or promoting data.

Current documentation is indexed in [`docs/README.md`](docs/README.md).
Versioned intelligence notes and reorganization phase records are preserved for
archaeology but are not current operating instructions.
