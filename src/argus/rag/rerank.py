"""Cross-encoder reranking with bge-reranker-v2-m3 (the optional 'rerank' extra).

A second-stage reranker scores each (query, passage) pair jointly — far more
accurate than first-stage ANN/FTS, but O(candidates), so it only ever runs over
the fused candidate pool, never the corpus. The model loads lazily and runs in a
worker thread so its synchronous forward pass never blocks the event loop.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)

_MAX_LENGTH: int = 1024


@lru_cache(maxsize=1)
def _load_model() -> Any:
    try:
        import torch  # ty: ignore[unresolved-import]
        from sentence_transformers import CrossEncoder  # ty: ignore[unresolved-import]
    except ModuleNotFoundError as error:
        raise RuntimeError("reranking needs the 'rerank' extra: uv sync --extra rerank") from error
    settings = get_settings()
    device: str = "mps" if torch.backends.mps.is_available() else "cpu"
    model = CrossEncoder(
        settings.rerank_model,
        device=device,
        activation_fn=torch.nn.Sigmoid(),
        max_length=_MAX_LENGTH,
    )
    log.info("rerank_model_loaded", model=settings.rerank_model, device=device)
    return model


def _score_sync(query: str, passages: list[str]) -> list[float]:
    model = _load_model()
    pairs: list[tuple[str, str]] = [(query, passage) for passage in passages]
    scores = model.predict(pairs, show_progress_bar=False, convert_to_numpy=True)
    return [float(score) for score in scores]


async def rerank(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    return await asyncio.to_thread(_score_sync, query, passages)
