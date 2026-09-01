# Market Intelligence v2.6

This patch activates the real NLP path for contextual event extraction.

## What changed

- FinBERT sentiment now supports batched scoring and caching.
- FinBERT can use CUDA when PyTorch sees a GPU.
- Sentence-transformer clustering can use configurable embedding models.
- Added `check_intelligence_nlp.py` to inspect optional NLP dependencies.
- Added `run_nlp_event_smoke.py` for small FinBERT + embedding smoke tests.
- Added `requirements-intelligence-nlp.txt` for optional installs.

## Runtime modes

The pipeline still supports heuristic mode:

- `--sentiment-backend heuristic`
- `--cluster-backend heuristic`

The semantic mode uses NLP models:

- `--sentiment-backend finbert`
- `--cluster-backend sentence-transformers`

`auto` attempts NLP first and falls back to heuristic mode when dependencies are missing.

## Useful environment variables

- `INTELLIGENCE_FINBERT_MODEL`: default `ProsusAI/finbert`
- `INTELLIGENCE_FINBERT_BATCH_SIZE`: default `16`
- `INTELLIGENCE_NLP_DEVICE`: `auto`, `cpu`, or `cuda`
- `INTELLIGENCE_EMBEDDING_MODEL`: default `sentence-transformers/all-MiniLM-L6-v2`
- `INTELLIGENCE_EMBEDDING_BATCH_SIZE`: default `64`

## Important limitation

This improves current/live semantic understanding. It does not create a valid
historical news backtest by itself.

For historical ML training, we still need a point-in-time historical news dataset:

- article text
- source
- published timestamp
- URL/source identifier
- ticker/topic mapping

Then each historical signal date can only use articles published before that date.
