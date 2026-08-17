from __future__ import annotations

import hashlib
import os
import re
import sys
from collections import defaultdict

import numpy as np

from ..events.event_schemas import MarketEvent


def tokenize(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()) if tok}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def fallback_cluster_events(events: list[MarketEvent], threshold: float = 0.35) -> list[MarketEvent]:
    clusters: list[tuple[str, set[str]]] = []
    for event in events:
        terms = tokenize(f"{event.event_type} {event.scope} {event.text}")
        assigned = None
        for cluster_id, cluster_terms in clusters:
            if jaccard(terms, cluster_terms) >= threshold:
                assigned = cluster_id
                cluster_terms.update(terms)
                break
        if assigned is None:
            raw = f"{event.event_type}|{event.scope}|{' '.join(sorted(list(terms))[:20])}"
            assigned = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
            clusters.append((assigned, set(terms)))
        event.cluster_id = assigned
    return events


def sentence_transformer_cluster_events(events: list[MarketEvent], threshold: float = 0.72) -> list[MarketEvent]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return fallback_cluster_events(events)

    if not events:
        return events
    model_name = os.environ.get("INTELLIGENCE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    batch_size = int(os.environ.get("INTELLIGENCE_EMBEDDING_BATCH_SIZE", "64"))
    device = os.environ.get("INTELLIGENCE_EMBEDDING_DEVICE", "cpu")
    if device == "auto":
        device = None
    model = SentenceTransformer(model_name, device=device)
    texts = [f"{event.event_type} {event.scope} {event.text}" for event in events]
    try:
        embeddings = np.asarray(model.encode(texts, normalize_embeddings=True, batch_size=batch_size))
    except RuntimeError as exc:
        if "out of memory" not in str(exc).lower():
            raise
        print(
            "[semantic-cluster-warning] CUDA out of memory during embedding; retrying on CPU.",
            file=sys.stderr,
        )
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        model = SentenceTransformer(model_name, device="cpu")
        embeddings = np.asarray(model.encode(texts, normalize_embeddings=True, batch_size=max(1, min(batch_size, 16))))
    cluster_ids: list[str | None] = [None] * len(events)
    cluster_count = 0
    for idx in range(len(events)):
        if cluster_ids[idx] is not None:
            continue
        cluster_id = f"sem_{cluster_count:04d}"
        cluster_count += 1
        cluster_ids[idx] = cluster_id
        sims = embeddings @ embeddings[idx]
        for jdx, sim in enumerate(sims):
            if cluster_ids[jdx] is None and float(sim) >= threshold:
                cluster_ids[jdx] = cluster_id
    for event, cluster_id in zip(events, cluster_ids):
        event.cluster_id = cluster_id
    return events


def cluster_events(events: list[MarketEvent], backend: str = "auto") -> list[MarketEvent]:
    if backend == "sentence-transformers":
        return sentence_transformer_cluster_events(events)
    if backend == "heuristic":
        return fallback_cluster_events(events)
    return sentence_transformer_cluster_events(events)


def cluster_summary(events: list[MarketEvent]) -> list[dict]:
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in events:
        grouped[event.cluster_id or "unclustered"].append(event)
    rows: list[dict] = []
    for cluster_id, items in grouped.items():
        signed = [event.signed_impact() for event in items]
        rows.append(
            {
                "cluster_id": cluster_id,
                "events": len(items),
                "queries": ",".join(sorted({event.query for event in items})),
                "event_types": ",".join(sorted({event.event_type for event in items})),
                "scopes": ",".join(sorted({event.scope for event in items})),
                "mean_signed_impact": round(float(np.mean(signed)) if signed else 0.0, 6),
                "max_abs_impact": round(float(np.max(np.abs(signed))) if signed else 0.0, 6),
                "sample_title": items[0].source_title,
            }
        )
    return sorted(rows, key=lambda row: abs(row["max_abs_impact"]), reverse=True)
