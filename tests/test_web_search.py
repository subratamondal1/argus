from __future__ import annotations

import httpx
import respx

from argus.config import get_settings
from argus.tools.registry import ToolCall, ToolRegistry
from argus.tools.web_search import register_web_search


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_web_search(registry)
    return registry


async def test_parses_results() -> None:
    settings = get_settings()
    with respx.mock:
        respx.get(f"{settings.searxng_url}/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"title": "T1", "url": "https://a", "content": "snippet 1"},
                        {"title": "T2", "url": "https://b", "content": "snippet 2"},
                    ]
                },
            )
        )
        result = await _registry().dispatch(
            ToolCall(name="web_search", arguments={"query": "hello", "max_results": 5})
        )

    assert result.ok
    assert result.content.query == "hello"
    assert len(result.content.hits) == 2
    assert result.content.hits[0].url == "https://a"


async def test_respects_max_results() -> None:
    settings = get_settings()
    with respx.mock:
        respx.get(f"{settings.searxng_url}/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"title": f"T{i}", "url": f"https://{i}", "content": "c"} for i in range(10)
                    ]
                },
            )
        )
        result = await _registry().dispatch(
            ToolCall(name="web_search", arguments={"query": "x", "max_results": 3})
        )

    assert result.ok
    assert len(result.content.hits) == 3
