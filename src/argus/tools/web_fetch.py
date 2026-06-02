"""The web_fetch tool: fetch a URL and extract its main text content."""

from __future__ import annotations

import httpx
import trafilatura
from pydantic import BaseModel, Field

from argus.config import get_settings
from argus.logging import get_logger
from argus.tools.registry import Permission, ToolRegistry

log = get_logger(__name__)

_USER_AGENT: str = (
    "Mozilla/5.0 (compatible; ArgusResearch/0.1; +https://github.com/subratamondal1/argus)"
)
_MAX_CHARS: int = 6000


class WebFetchArgs(BaseModel):
    url: str = Field(description="The URL to fetch and read.")


class WebFetchResult(BaseModel):
    url: str = Field(description="The URL that was fetched.")
    text: str = Field(description="Extracted main text content, possibly truncated.")
    truncated: bool = Field(description="Whether the text was truncated to fit the budget.")


def register_web_fetch(registry: ToolRegistry) -> None:
    @registry.tool(permission=Permission.ALLOW)
    async def web_fetch(args: WebFetchArgs) -> WebFetchResult:
        """Fetch a web page and return its main text content.

        Use this after web_search to read the actual content of the most
        authoritative result instead of trusting the short search snippet.
        """
        settings = get_settings()
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_s,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response: httpx.Response = await client.get(args.url)
            response.raise_for_status()

        extracted: str | None = trafilatura.extract(response.text, include_comments=False)
        text: str = (extracted or "").strip()
        truncated: bool = len(text) > _MAX_CHARS
        log.info("web_fetch", url=args.url, chars=len(text), truncated=truncated)
        return WebFetchResult(url=args.url, text=text[:_MAX_CHARS], truncated=truncated)
