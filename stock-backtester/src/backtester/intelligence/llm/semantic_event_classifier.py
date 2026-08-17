from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np


EVENT_TYPE_DESCRIPTIONS = {
    "price_action": [
        "The stock price moved, broke a level, hit a high or low, fell, rallied, or underperformed peers.",
        "Shares are trading lower, below support, above a buy point, or in a losing streak.",
    ],
    "rates": [
        "Interest rates, Treasury yields, bond yields, Federal Reserve policy, or FOMC expectations affect markets.",
        "Higher or lower rates change valuation and risk appetite.",
    ],
    "inflation": [
        "Inflation, CPI, PCE, prices, disinflation, or inflation expectations affect markets.",
    ],
    "earnings": [
        "Reported earnings, EPS, revenue, profit, margins, quarterly results, or financial performance.",
    ],
    "guidance": [
        "Management outlook, forecast, raised guidance, lowered guidance, future revenue or earnings expectations.",
    ],
    "valuation": [
        "Valuation, multiples, price-to-sales, P/E, expensive stocks, multiple compression, or valuation concerns.",
    ],
    "liquidity": [
        "Liquidity, credit spreads, fund flows, risk-on or risk-off rotation, ETF flows, market plumbing.",
    ],
    "legal": [
        "Lawsuit, investigation, probe, DOJ, FTC, SEC charges, antitrust, legal or regulatory enforcement.",
    ],
    "geopolitical": [
        "War, sanctions, tariffs, election, geopolitical conflict, government action, Iran, China, White House, Congress.",
    ],
    "sector_rotation": [
        "A sector, industry, peer group, or market basket is rotating, outperforming, underperforming, or pressured.",
    ],
    "commodity": [
        "Oil, crude, natural gas, gold, copper, commodity prices, or energy commodities affect markets.",
    ],
    "company_fundamental": [
        "Business fundamentals, demand, contracts, orders, backlog, customers, products, growth, cash flow.",
    ],
    "analyst_rating": [
        "Analyst upgrade, downgrade, price target, rating change, Wall Street recommendation.",
    ],
    "m_and_a": [
        "Merger, acquisition, takeover, strategic investment, divestiture, spin-off, deal news.",
    ],
    "general_news": [
        "General market or company news that does not clearly fit a more specific financial event type.",
    ],
}


SCOPE_DESCRIPTIONS = {
    "ticker": [
        "The sentence is mainly about one specific company or ticker.",
        "Company-specific stock, business, earnings, guidance, or legal event.",
    ],
    "peer_group": [
        "The sentence compares the company against direct competitors or peers.",
    ],
    "sector": [
        "The sentence is mainly about an industry or sector such as software, banks, utilities, energy, retail, semiconductors.",
    ],
    "index": [
        "The sentence is mainly about a stock index or ETF such as Nasdaq, QQQ, S&P 500, SPY, Russell, Dow.",
    ],
    "macro": [
        "The sentence is mainly about economy-wide conditions, rates, inflation, Fed policy, recession, dollar, or yields.",
    ],
    "political": [
        "The sentence is mainly about government, elections, tariffs, sanctions, war, geopolitical risk, Congress, White House.",
    ],
    "commodity": [
        "The sentence is mainly about oil, gas, gold, copper, or other commodity markets.",
    ],
    "unknown": [
        "The sentence does not clearly identify a market scope.",
    ],
}


@dataclass(slots=True)
class EventClassification:
    event_type: str
    scope: str
    event_type_confidence: float
    scope_confidence: float
    classifier_model: str


class SemanticEventClassifier:
    def __init__(
        self,
        *,
        model_name: str | None = None,
        device: str | None = None,
        min_confidence: float = 0.20,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is required for semantic event classification") from exc

        self.model_name = model_name or os.environ.get(
            "INTELLIGENCE_EVENT_CLASSIFIER_MODEL",
            os.environ.get("INTELLIGENCE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        )
        self.device = device or os.environ.get("INTELLIGENCE_EVENT_CLASSIFIER_DEVICE", "cpu")
        if self.device == "auto":
            self.device = None
        self.min_confidence = min_confidence
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.event_labels, self.event_embeddings = self._embed_label_descriptions(EVENT_TYPE_DESCRIPTIONS)
        self.scope_labels, self.scope_embeddings = self._embed_label_descriptions(SCOPE_DESCRIPTIONS)

    def _embed_label_descriptions(self, descriptions: dict[str, list[str]]) -> tuple[list[str], np.ndarray]:
        labels = list(descriptions.keys())
        texts = [" ".join(descriptions[label]) for label in labels]
        embeddings = np.asarray(self.model.encode(texts, normalize_embeddings=True))
        return labels, embeddings

    def classify_many(
        self,
        texts: list[str],
        *,
        fallback_event_types: list[str] | None = None,
        fallback_scopes: list[str] | None = None,
    ) -> list[EventClassification]:
        if not texts:
            return []
        batch_size = int(os.environ.get("INTELLIGENCE_EVENT_CLASSIFIER_BATCH_SIZE", "64"))
        text_embeddings = np.asarray(self.model.encode(texts, normalize_embeddings=True, batch_size=batch_size))
        event_sims = text_embeddings @ self.event_embeddings.T
        scope_sims = text_embeddings @ self.scope_embeddings.T
        out: list[EventClassification] = []
        for idx in range(len(texts)):
            event_idx = int(np.argmax(event_sims[idx]))
            scope_idx = int(np.argmax(scope_sims[idx]))
            event_conf = float(max(0.0, min(1.0, (event_sims[idx, event_idx] + 1.0) / 2.0)))
            scope_conf = float(max(0.0, min(1.0, (scope_sims[idx, scope_idx] + 1.0) / 2.0)))

            event_type = self.event_labels[event_idx]
            scope = self.scope_labels[scope_idx]
            if event_conf < self.min_confidence and fallback_event_types:
                event_type = fallback_event_types[idx]
            if scope_conf < self.min_confidence and fallback_scopes:
                scope = fallback_scopes[idx]

            out.append(
                EventClassification(
                    event_type=event_type,
                    scope=scope,
                    event_type_confidence=round(event_conf, 4),
                    scope_confidence=round(scope_conf, 4),
                    classifier_model=f"semantic:{self.model_name}",
                )
            )
        return out


class HeuristicEventClassifier:
    classifier_model = "heuristic"

    def classify_many(
        self,
        texts: list[str],
        *,
        fallback_event_types: list[str] | None = None,
        fallback_scopes: list[str] | None = None,
    ) -> list[EventClassification]:
        return [
            EventClassification(
                event_type=(fallback_event_types or ["general_news"] * len(texts))[idx],
                scope=(fallback_scopes or ["unknown"] * len(texts))[idx],
                event_type_confidence=0.0,
                scope_confidence=0.0,
                classifier_model="heuristic",
            )
            for idx in range(len(texts))
        ]


def make_event_classifier(name: str, *, device: str | None = None, min_confidence: float = 0.20):
    if name == "semantic":
        return SemanticEventClassifier(device=device, min_confidence=min_confidence)
    if name == "auto":
        try:
            return SemanticEventClassifier(device=device, min_confidence=min_confidence)
        except RuntimeError:
            return HeuristicEventClassifier()
    return HeuristicEventClassifier()
