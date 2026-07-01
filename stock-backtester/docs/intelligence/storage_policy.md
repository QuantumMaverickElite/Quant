# Intelligence Storage Policy

The intelligence pipeline must stay lightweight on the main laptop.

## Rules

- Do not store local LLM weights in this repo.
- Prefer API-based LLM classification for article/event extraction.
- Never commit API keys, raw secrets, or local `.env` files.
- Keep raw provider payloads bounded by retention windows.
- Keep model artifacts small unless a run is explicitly promoted.
- Training runs should be pruned, compressed, or moved out of the repo when stale.
- Generated outputs should be reproducible from scripts/configs where possible.

## Current Direction

Use remote/API LLMs only for structured event extraction.

The local repo stores:

- normalized events
- compact feature tables
- compact labels
- small model reports
- promoted model artifacts only

The local repo should not store:

- large LLM models
- unlimited raw API caches
- unbounded training runs
- repeated duplicate output copies

## Recommended Retention

- raw worker cache: 30 days
- unpromoted training runs: 7 to 14 days
- promoted model reports: keep
- promoted compact artifacts: keep
- obsolete exploratory runs: delete or move outside repo
