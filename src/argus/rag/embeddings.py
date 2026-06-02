"""Local text embeddings via native Ollama (/api/embed), with a LiteLLM fallback.

nomic-embed-text is asymmetric: documents and queries are embedded with different
task prefixes (search_document: / search_query:). Ollama's HTTP API does not add
these prefixes itself, so they are applied at the call site here. Embeddings are
768-dimensional to match the chunks.embedding vector(768) column.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import httpx
import litellm

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)

EMBEDDING_DIM: int = 768


class EmbedTask(StrEnum):
    DOCUMENT = "search_document"
    QUERY = "search_query"


def _prefixed(texts: list[str], task: EmbedTask) -> list[str]:
    return [f"{task.value}: {text}" for text in texts]


def _ensure_dims(embeddings: list[list[float]]) -> None:
    for vector in embeddings:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(f"expected {EMBEDDING_DIM}-dim embeddings, got {len(vector)}")


async def embed_texts(texts: list[str], *, task: EmbedTask) -> list[list[float]]:
    if not texts:
        return []
    inputs: list[str] = _prefixed(texts, task)
    settings = get_settings()
    try:
        embeddings: list[list[float]] = await _embed_via_ollama(
            inputs,
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
            timeout_s=settings.request_timeout_s,
        )
    except (httpx.HTTPError, KeyError) as error:
        log.warning("ollama_embed_failed_falling_back", error=str(error))
        embeddings = await _embed_via_litellm(inputs, model=settings.embedding_model)
    _ensure_dims(embeddings)
    log.info("embed", task=task.value, n=len(embeddings))
    return embeddings


async def _embed_via_ollama(
    inputs: list[str], *, model: str, base_url: str, timeout_s: float
) -> list[list[float]]:
    model_tag: str = model.removeprefix("ollama/")
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response: httpx.Response = await client.post(
            f"{base_url}/api/embed",
            json={"model": model_tag, "input": inputs},
        )
        response.raise_for_status()
        payload: Any = response.json()
    embeddings: Any = payload["embeddings"]
    if not isinstance(embeddings, list):
        raise ValueError("ollama /api/embed returned no embeddings array")
    return [[float(value) for value in vector] for vector in embeddings]


async def _embed_via_litellm(inputs: list[str], *, model: str) -> list[list[float]]:
    response: Any = await litellm.aembedding(model=model, input=inputs)
    return [[float(value) for value in item["embedding"]] for item in response.data]
