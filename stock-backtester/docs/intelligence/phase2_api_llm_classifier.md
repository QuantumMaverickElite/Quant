# Phase 2A: API LLM Event Classifier

## Status

Phase 2A adds an API-compatible LLM classification scaffold.

The classifier can run in two modes:

- mock: local keyword scaffold for pipeline testing
- api: OpenAI-compatible HTTP API mode

No local LLM weights are required.

## Architecture

event_fact_table
-> classify_event_facts_llm.py
-> llm_event_classifications
-> join_llm_classifications.py
-> event_impact_dataset_with_llm
-> event_day_impact_dataset_with_llm
-> baseline smoke test

## Design Rule

The LLM does not decide allocation.

The LLM only extracts structured features:

- event type
- event subtype
- direction
- scope
- time horizon
- risk flags
- sentiment score
- materiality score
- novelty score
- catalyst strength
- confidence

ML must learn whether these fields matter historically.

Allocator integration remains blocked until walk-forward validation.

## API Environment Variables

API mode uses OpenAI-compatible variables:

- OPENAI_COMPAT_API_BASE
- OPENAI_COMPAT_API_KEY
- OPENAI_COMPAT_MODEL

These must stay outside git.

## Current Validation

Mock classification ran successfully.

LLM classifications joined into the event-level impact dataset.

LLM features aggregated into the ticker-day impact dataset.

Baseline training smoke test confirmed that LLM-derived features flow into the model pipeline.

This is not yet a trusted trading model.

## Gemini Smoke Test

Gemini API smoke test succeeded with:

- provider: Google Gemini API
- base: https://generativelanguage.googleapis.com/v1beta/openai
- model: gemini-2.5-flash-lite
- rows: 5
- status: valid JSON classifications returned

`gemini-3.5-flash` returned HTTP 503 during the first test due to temporary high demand, so `gemini-2.5-flash-lite` is the current practical default for lightweight bulk classification.

Recommended use:

- gemini-2.5-flash-lite for bulk event classification
- stronger Gemini model later for difficult/ambiguous articles

## GitHub Models Smoke Test

GitHub Models API smoke test succeeded with:

- provider: GitHub Models
- base: https://models.github.ai/inference
- model: openai/gpt-4.1
- rows: 5
- status: valid JSON classifications returned

Initial Gemini vs GitHub comparison:

- Gemini: gemini-2.5-flash-lite
- GitHub Models: openai/gpt-4.1
- event type agreement: 1.0 on the 5-row smoke sample
- direction agreement: 0.8 on the 5-row smoke sample

Interpretation:

- Gemini Flash-Lite is likely good for low-cost bulk classification.
- GitHub GPT-4.1 is likely better for higher-quality validation and ambiguous articles.
- Both should be benchmarked on 25 to 100 mixed articles before selecting a default production classifier.

## Mixed 50 Benchmark Attempt

A mixed 50-row benchmark sample was created to avoid first-row ticker/event bias.

Initial GitHub Models GPT-4.1 mixed benchmark behavior:

- mixed sample rows: 50
- successful partial classifications before throttling: 20
- provider throttling: HTTP 429 after repeated requests
- partial-save behavior worked and preserved progress
- conclusion: production classification needs resume-safe chunking and provider-aware cooldowns

Operational policy:

- Do not run large LLM classification batches as one continuous command.
- Prefer small chunks with long cooldowns.
- Treat HTTP 429 from GitHub Models as a hard cooldown signal.
- Preserve partial outputs and resume from unclassified event IDs.
