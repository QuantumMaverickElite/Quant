# Market Intelligence v2.6.1

This patch fixes NLP GPU memory pressure on smaller GPUs.

## What changed

- Sentence-transformer clustering defaults to CPU through
  `INTELLIGENCE_EMBEDDING_DEVICE=cpu`.
- If embedding on CUDA runs out of memory, clustering retries on CPU.
- `run_nlp_event_smoke.py` now accepts:
  - `--nlp-device auto|cpu|cuda`
  - `--embedding-device auto|cpu|cuda`
- `extract_contextual_events.py` now accepts the same device flags.
- `check_intelligence_nlp.py` reports configured FinBERT and embedding devices.

## Recommended local setup

For a small GPU, use:

- FinBERT sentiment on CUDA
- sentence-transformer clustering on CPU

That keeps the core sentiment model accelerated without loading both models into
GPU memory at the same time.
