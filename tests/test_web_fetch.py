from __future__ import annotations

import httpx
import respx

from argus.tools.registry import ToolCall, ToolRegistry
from argus.tools.web_fetch import register_web_fetch

_ARTICLE_HTML: str = """
<html><head><title>Introducing Claude Opus 4.8</title></head>
<body><article>
<h1>Introducing Claude Opus 4.8</h1>
<p>Today we are announcing Claude Opus 4.8, our most capable model to date. Claude
Opus 4.8 improves on Claude Opus 4.7 across coding, agentic tasks, reasoning, and
practical knowledge work. It is available in the API and in the Claude apps today,
and continues our focus on building reliable, interpretable, and steerable systems
for developers and enterprises around the world.</p>
</article></body></html>
"""


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_web_fetch(registry)
    return registry


async def test_fetch_extracts_main_text() -> None:
    with respx.mock:
        respx.get("https://example.com/opus").mock(
            return_value=httpx.Response(200, text=_ARTICLE_HTML)
        )
        result = await _registry().dispatch(
            ToolCall(name="web_fetch", arguments={"url": "https://example.com/opus"})
        )

    assert result.ok
    assert result.content.url == "https://example.com/opus"
    assert "Claude Opus 4.8" in result.content.text
    assert result.content.truncated is False


async def test_fetch_http_error_is_a_failed_result() -> None:
    with respx.mock:
        respx.get("https://example.com/missing").mock(return_value=httpx.Response(404))
        result = await _registry().dispatch(
            ToolCall(name="web_fetch", arguments={"url": "https://example.com/missing"})
        )

    assert not result.ok
