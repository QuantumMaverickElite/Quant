from __future__ import annotations

from .claim_extractor import extract_claims
from .evidence_graph import evidence_graph_features, orthogonalize_claims
from .evidence_scorer import aggregate_sentiment, confidence_score, dominant_pressure, pressure_features
from .regime_break_scorer import regime_action, regime_break_score
from .schemas import IntelligenceReport, SourceDocument


class MarketIntelligenceEngine:
    def analyze(
        self,
        query: str,
        documents: list[SourceDocument],
        *,
        peer_divergence: float = 0.0,
        volume_shock: float = 0.0,
        trend_damage: float = 0.0,
    ) -> IntelligenceReport:
        raw_claims = extract_claims(query, documents)
        claims, events = orthogonalize_claims(raw_claims)
        sentiment = aggregate_sentiment(claims)
        features = pressure_features(claims)
        graph_features = evidence_graph_features(events, raw_claim_count=len(raw_claims))
        break_score = regime_break_score(
            claims,
            features,
            peer_divergence=peer_divergence,
            volume_shock=volume_shock,
            trend_damage=trend_damage,
        )
        confidence = confidence_score(claims)

        bullish = [claim for claim in claims if claim.direction == "bullish"]
        bearish = [claim for claim in claims if claim.direction == "bearish"]
        neutral = [claim for claim in claims if claim.direction == "neutral"]

        action = regime_action(break_score)
        pressure = dominant_pressure(features)
        horizon = self._dominant_horizon(claims)
        summary = self._build_summary(query, sentiment, break_score, pressure, action, len(claims), len(events))

        model_features = {
            **features,
            **graph_features,
            "sentiment_score": sentiment,
            "regime_break_score": break_score,
            "confidence": confidence,
            "peer_divergence": peer_divergence,
            "volume_shock": volume_shock,
            "trend_damage": trend_damage,
        }

        return IntelligenceReport(
            query=query.upper(),
            as_of=IntelligenceReport.now_iso(),
            sentiment_score=round(sentiment, 4),
            regime_break_score=round(break_score, 4),
            confidence=round(confidence, 4),
            dominant_pressure=pressure,
            time_horizon=horizon,
            summary=summary,
            bullish_evidence=bullish[:8],
            bearish_evidence=bearish[:8],
            neutral_evidence=neutral[:8],
            model_features={key: round(float(value), 4) for key, value in model_features.items()},
        )

    @staticmethod
    def _dominant_horizon(claims) -> str:
        if not claims:
            return "unknown"
        counts = {}
        for claim in claims:
            counts[claim.time_horizon] = counts.get(claim.time_horizon, 0) + 1
        return max(counts, key=counts.get)

    @staticmethod
    def _build_summary(
        query: str,
        sentiment: float,
        break_score: float,
        pressure: str,
        action: str,
        n_claims: int,
        n_events: int,
    ) -> str:
        if n_claims == 0:
            return f"No usable evidence found for {query.upper()}."

        tone = "bullish" if sentiment > 0.15 else "bearish" if sentiment < -0.15 else "mixed/neutral"
        if break_score < 0.30:
            regime = "Evidence points more toward normal volatility inside the existing regime."
        elif break_score < 0.55:
            regime = "Evidence is mixed; avoid adding until the setup becomes clearer."
        elif break_score < 0.75:
            regime = "Evidence suggests possible regime damage; averaging down is not favored."
        else:
            regime = "Evidence suggests high thesis-break risk; reduce exposure or wait for a new setup."

        return (
            f"{query.upper()} evidence is {tone}, with dominant pressure from {pressure}. "
            f"{regime} Action label: {action}. Evidence: {n_claims} claims collapsed into {n_events} events."
        )
