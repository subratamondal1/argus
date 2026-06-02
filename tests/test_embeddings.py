from __future__ import annotations

import httpx
import orjson
import pytest
import respx

from argus.config import get_settings
from argus.rag.embeddings import EMBEDDING_DIM, EmbedTask, _ensure_dims, _prefixed, embed_texts


def test_prefixes_are_task_specific() -> None:
    assert _prefixed(["hi"], EmbedTask.QUERY) == ["search_query: hi"]
    assert _prefixed(["hi"], EmbedTask.DOCUMENT) == ["search_document: hi"]


def test_ensure_dims_rejects_wrong_width() -> None:
    with pytest.raises(ValueError):
        _ensure_dims([[0.0, 1.0, 2.0]])


async def test_empty_input_skips_the_network() -> None:
    assert await embed_texts([], task=EmbedTask.QUERY) == []


async def test_embed_calls_ollama_with_prefixed_input_and_returns_768d() -> None:
    settings = get_settings()
    with respx.mock:
        route = respx.post(f"{settings.ollama_base_url}/api/embed").mock(
            return_value=httpx.Response(200, json={"embeddings": [[0.1] * EMBEDDING_DIM]})
        )
        vectors = await embed_texts(["the capital of France"], task=EmbedTask.QUERY)

    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIM
    body = orjson.loads(route.calls.last.request.content)
    assert body["model"] == "nomic-embed-text"
    assert body["input"] == ["search_query: the capital of France"]
