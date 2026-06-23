# Market Intelligence v1.9.1

Broadcasts global contextual event features.

When v1.8.1 extracts macro/index/sector events once under `MARKET`, v1.9.1 merges those values into ticker rows as market context:

- `market_macro_event_pressure`
- `market_rates_event_pressure`
- `market_index_event_pressure`
- `market_contextual_event_risk`

This keeps extraction fast without losing broad market context.
