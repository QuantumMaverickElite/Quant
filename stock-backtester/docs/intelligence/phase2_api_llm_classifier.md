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
