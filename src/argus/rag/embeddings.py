"""Text embeddings, dual-mode: native Ollama for local models, LiteLLM for APIs.

An `ollama/` embedding model is served by native Ollama over /api/embed; anything
else (e.g. openai/text-embedding-3-small) goes through litellm with an explicit
output dimension so it matches the chunks.embedding vector(768) column. Local
nomic-embed-text is asymmetric, so on that path documents and queries get their
task prefixes (search_document: / search_query:), which Ollama does not add; API
models embed the raw text.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import httpx
import litellm

from argus.config import Settings, get_settings
from argus.logging import get_logger

log = get_logger(__name__)

EMBEDDING_DIM: int = 768


class EmbedTask(StrEnum):
    DOCUMENT = "search_document"
    QUERY = "search_query"


def _prefixed(texts: list[str], task: EmbedTask) -> list[str]:
    return [f"{task.value}: {text}" for text in texts]


def _ensure_dims(embeddings: list[list[float]], expected: int) -> None:
    for vector in embeddings:
        if len(vector) != expected:
            raise ValueError(f"expected {expected}-dim embeddings, got {len(vector)}")


async def embed_texts(texts: list[str], *, task: EmbedTask) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    if settings.embedding_model.startswith("ollama/"):
        embeddings: list[list[float]] = await _embed_local(texts, task=task, settings=settings)
    else:
        embeddings = await _embed_via_litellm(
            texts, model=settings.embedding_model, dimensions=settings.embedding_dimensions
        )
    _ensure_dims(embeddings, settings.embedding_dimensions)
    log.info("embed", task=task.value, model=settings.embedding_model, n=len(embeddings))
    return embeddings


async def _embed_local(
    texts: list[str], *, task: EmbedTask, settings: Settings
) -> list[list[float]]:
    inputs: list[str] = _prefixed(texts, task)
    try:
        return await _embed_via_ollama(
            inputs,
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
            timeout_s=settings.request_timeout_s,
        )
    except (httpx.HTTPError, KeyError) as error:
        log.warning("ollama_embed_failed_falling_back", error=str(error))
        return await _embed_via_litellm(inputs, model=settings.embedding_model, dimensions=None)


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


async def _embed_via_litellm(
    inputs: list[str], *, model: str, dimensions: int | None
) -> list[list[float]]:
    kwargs: dict[str, Any] = {"model": model, "input": inputs}
    if dimensions is not None:
        kwargs["dimensions"] = dimensions
    response: Any = await litellm.aembedding(**kwargs)
    return [[float(value) for value in item["embedding"]] for item in response.data]
