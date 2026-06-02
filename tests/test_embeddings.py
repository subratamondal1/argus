from __future__ import annotations

from typing import Any

import httpx
import orjson
import pytest
import respx

from argus.config import get_settings
from argus.rag import embeddings as embeddings_mod
from argus.rag.embeddings import EMBEDDING_DIM, EmbedTask, _ensure_dims, _prefixed, embed_texts


def test_prefixes_are_task_specific() -> None:
    assert _prefixed(["hi"], EmbedTask.QUERY) == ["search_query: hi"]
    assert _prefixed(["hi"], EmbedTask.DOCUMENT) == ["search_document: hi"]


def test_ensure_dims_rejects_wrong_width() -> None:
    with pytest.raises(ValueError):
        _ensure_dims([[0.0, 1.0, 2.0]], 768)


async def test_empty_input_skips_the_network() -> None:
    assert await embed_texts([], task=EmbedTask.QUERY) == []


async def test_embed_calls_ollama_with_prefixed_input_and_returns_768d(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_settings() -> Any:
        return get_settings().model_copy(update={"embedding_model": "ollama/nomic-embed-text"})

    monkeypatch.setattr(embeddings_mod, "get_settings", fake_settings)
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


async def test_api_model_routes_through_litellm_with_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeResponse:
        def __init__(self) -> None:
            self.data: list[dict[str, Any]] = [{"embedding": [0.0] * EMBEDDING_DIM}]

    async def fake_aembedding(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return _FakeResponse()

    def fake_settings() -> Any:
        return get_settings().model_copy(
            update={"embedding_model": "openai/text-embedding-3-small", "embedding_dimensions": 768}
        )

    monkeypatch.setattr(embeddings_mod, "get_settings", fake_settings)
    monkeypatch.setattr(embeddings_mod.litellm, "aembedding", fake_aembedding)

    vectors = await embed_texts(["hello"], task=EmbedTask.DOCUMENT)

    assert len(vectors[0]) == EMBEDDING_DIM
    assert captured["model"] == "openai/text-embedding-3-small"
    assert captured["dimensions"] == 768
    assert captured["input"] == ["hello"]


async def test_unreachable_ollama_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_settings() -> Any:
        return get_settings().model_copy(update={"embedding_model": "ollama/nomic-embed-text"})

    async def refuse(*args: Any, **kwargs: Any) -> Any:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(embeddings_mod, "get_settings", fake_settings)
    monkeypatch.setattr(embeddings_mod, "_embed_via_ollama", refuse)

    with pytest.raises(RuntimeError, match="Ollama"):
        await embed_texts(["hi"], task=EmbedTask.QUERY)
