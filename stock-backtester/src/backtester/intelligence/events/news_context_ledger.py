from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd

from .event_schemas import MarketEvent


def parse_time(value: str | None) -> pd.Timestamp:
    if not value:
        return pd.NaT
    return pd.to_datetime(value, errors="coerce", utc=True)


def event_time(event: MarketEvent) -> pd.Timestamp:
    parsed = parse_time(event.published_at)
    if pd.isna(parsed):
        return pd.Timestamp(datetime.now(timezone.utc))
    return parsed


def apply_contextual_novelty(events: list[MarketEvent]) -> list[MarketEvent]:
    if not events:
        return events
    events = sorted(events, key=event_time)
    seen_by_key: dict[tuple[str, str, str], list[pd.Timestamp]] = defaultdict(list)
    seen_by_cluster: dict[str, list[pd.Timestamp]] = defaultdict(list)

    for event in events:
        ts = event_time(event)
        key = (event.query, event.event_type, event.scope)
        cluster_key = event.cluster_id or ""
        prior_times = seen_by_key[key] + seen_by_cluster.get(cluster_key, [])
        recent_30d = [t for t in prior_times if not pd.isna(t) and (ts - t).days <= 30]
        recent_7d = [t for t in prior_times if not pd.isna(t) and (ts - t).days <= 7]
        recent_1d = [t for t in prior_times if not pd.isna(t) and (ts - t).days <= 1]

        novelty = 0.80
        if recent_30d:
            novelty -= 0.20
        if recent_7d:
            novelty -= 0.20
        if recent_1d:
            novelty -= 0.15
        event.novelty = round(max(0.15, min(1.0, novelty)), 4)

        seen_by_key[key].append(ts)
        if cluster_key:
            seen_by_cluster[cluster_key].append(ts)
    return events


def context_windows(events: list[MarketEvent]) -> dict[str, dict]:
    if not events:
        return {}
    now = max(event_time(event) for event in events)
    windows = {"24h": 1, "7d": 7, "30d": 30}
    out: dict[str, dict] = {}
    for name, days in windows.items():
        subset = [event for event in events if not pd.isna(event_time(event)) and (now - event_time(event)).days <= days]
        out[name] = {
            "events": len(subset),
            "mean_signed_impact": round(sum(event.signed_impact() for event in subset) / max(1, len(subset)), 6),
            "macro_events": sum(1 for event in subset if event.scope == "macro"),
            "sector_events": sum(1 for event in subset if event.scope == "sector"),
            "ticker_events": sum(1 for event in subset if event.scope == "ticker"),
        }
    return out
