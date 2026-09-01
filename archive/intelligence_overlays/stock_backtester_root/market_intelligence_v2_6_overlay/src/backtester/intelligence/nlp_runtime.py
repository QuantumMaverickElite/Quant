from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class NlpRuntimeStatus:
    torch_installed: bool
    transformers_installed: bool
    sentence_transformers_installed: bool
    cuda_available: bool
    cuda_device_count: int
    finbert_model: str
    embedding_model: str
    finbert_load_ok: bool | None = None
    embedding_load_ok: bool | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def module_installed(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_nlp_runtime(*, load_models: bool = False) -> NlpRuntimeStatus:
    torch_installed = module_installed("torch")
    transformers_installed = module_installed("transformers")
    sentence_transformers_installed = module_installed("sentence_transformers")
    cuda_available = False
    cuda_device_count = 0
    error: str | None = None

    if torch_installed:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            cuda_device_count = int(torch.cuda.device_count()) if cuda_available else 0
        except Exception as exc:
            error = f"torch check failed: {exc}"

    status = NlpRuntimeStatus(
        torch_installed=torch_installed,
        transformers_installed=transformers_installed,
        sentence_transformers_installed=sentence_transformers_installed,
        cuda_available=cuda_available,
        cuda_device_count=cuda_device_count,
        finbert_model=os.environ.get("INTELLIGENCE_FINBERT_MODEL", "ProsusAI/finbert"),
        embedding_model=os.environ.get("INTELLIGENCE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        error=error,
    )

    if load_models:
        try:
            from .contextual_event_extractor import FinBertSentimentBackend

            backend = FinBertSentimentBackend()
            backend.score("The company raised guidance after strong revenue growth.")
            status.finbert_load_ok = True
        except Exception as exc:
            status.finbert_load_ok = False
            status.error = f"FinBERT load failed: {exc}"

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(status.embedding_model)
            model.encode(["rates rose", "earnings beat"], normalize_embeddings=True)
            status.embedding_load_ok = True
        except Exception as exc:
            status.embedding_load_ok = False
            status.error = f"{status.error}; embedding load failed: {exc}" if status.error else f"embedding load failed: {exc}"

    return status
