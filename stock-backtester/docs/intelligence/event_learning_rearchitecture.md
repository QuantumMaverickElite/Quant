# Intelligence Event-Learning Rearchitecture

## Problem

The previous intelligence layer mixed together three separate ideas:

1. NLP classification: what does the text say?
2. Event usefulness: did this kind of event historically matter?
3. Allocator adjustment: how much should position sizing change?

That is dangerous because heuristic NLP/rule scores can accidentally behave like learned truth.

## Correct Design

The new pipeline separates the layers:

raw provider payloads
-> normalized news/source rows
-> event fact table
-> NLP event extraction
-> forward outcome labels
-> event impact training dataset
-> ML event-impact model
-> bounded allocator overlay

## Core Principle

NLP should classify and structure information.

ML should learn whether that information mattered historically.

The allocator should only receive bounded model outputs.

## Required Tables

### event_fact_table

One row per ticker/article/event timestamp.

Required fields:

- event_id
- article_id
- ticker
- company_name
- cik
- published_at
- event_date
- provider
- source
- title
- summary
- url
- raw_file
- text

This table does not contain allocator weights.

### event_outcome_labels

Forward realized outcomes after each event.

Required fields:

- forward_return_1d
- forward_return_5d
- forward_return_20d
- forward_alpha_vs_spy_1d
- forward_alpha_vs_spy_5d
- forward_alpha_vs_spy_20d
- forward_drawdown_20d
- forward_volatility_20d

### event_impact_dataset

Join event facts, NLP features, market context, and outcome labels.

This is the table ML trains on.

### allocator_event_overlay

The allocator receives only bounded model outputs:

- event_alpha_score
- event_confidence
- event_risk_score

The overlay must clip its effect. News cannot hijack the allocator.

## Time Alignment Rule

No latest-per-ticker merge is allowed for historical training.

Every event feature must satisfy:

event_time <= signal_time
event_time inside lookback window

No future article or future feature can be merged into an older signal row.

## Legacy Policy

Existing heuristic intelligence modules are treated as legacy/fallback until this pipeline replaces them.

They may generate candidate features, but they should not directly determine allocator weights.

## LLM Direction

The project should prefer API-based LLM classification over local LLM hosting on the main laptop.

Reasons:

- The main machine is storage constrained.
- Local LLM weights are too large for the current workflow.
- LLMs should only extract structured event features.
- LLM outputs should not directly control allocation.
- API keys must stay outside git.
- Raw API responses and cached LLM outputs should have bounded retention.

Future LLM layer:

raw article text
-> API LLM classifier
-> structured event fields
-> event impact dataset
-> local ML model learns usefulness
-> bounded allocator overlay
