# Market Intelligence v2.7.4

This patch tightens the NLP event extraction layer.

Changes:

- Keeps ticker-owned events out of the broad `MARKET` stream when the final grounded scope is `ticker`.
- Treats ticker valuation events as ticker-owned, not peer-group events.
- Prevents adjacent sentence context from turning non-financial sentences into `earnings`.
- Keeps direct price-action language classified as `price_action`.
- Adds `--queries-file` to semantic extraction and smoke-test scripts.

Recommended use:

1. Generate a newline-delimited query file from the latest evaluated intelligence feature set.
2. Run semantic event extraction with FinBERT sentiment on CUDA and embeddings/classification on CPU.
3. Rebuild contextual event features, opportunity scores, allocator features, and diagnostics.
