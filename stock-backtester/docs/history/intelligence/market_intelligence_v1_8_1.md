# Market Intelligence v1.8.1

Speed hotfix for contextual event extraction.

## Fix

The old extractor ran every query against every source document and duplicated broad macro/sector/index events once per ticker.

The new default mode is:

```text
--mode fast
```

It:

- extracts ticker-specific events only from documents that mention the ticker
- extracts macro/sector/index/political events once under `MARKET`
- deduplicates repeated source documents/events

Use the old behavior only for debugging:

```text
--mode exhaustive
```
