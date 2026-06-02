"""The web_search tool backed by a self-hosted SearXNG instance."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from argus.config import get_settings
from argus.logging import get_logger
from argus.tools.registry import Permission, ToolRegistry

log = get_logger(__name__)


class WebSearchArgs(BaseModel):
    query: str = Field(description="The search query.")
    max_results: int = Field(default=8, ge=1, le=15, description="How many results to return.")


class SearchHit(BaseModel):
    title: str = Field(description="Result title.")
    url: str = Field(description="Result URL.")
    snippet: str = Field(description="Short content excerpt.")
    published: str = Field(default="", description="Publication date, if the engine reports one.")


class WebSearchResult(BaseModel):
    query: str = Field(description="The query that produced these hits.")
    hits: list[SearchHit] = Field(description="Results in rank order.")


def register_web_search(registry: ToolRegistry) -> None:
    @registry.tool(permission=Permission.ALLOW)
    async def web_search(args: WebSearchArgs) -> WebSearchResult:
        """Search the web and return the top results (title, url, snippet).

        Use this to find current, factual information before answering. Prefer
        searching over guessing whenever a question concerns real-world facts.
        """
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
            response: httpx.Response = await client.get(
                f"{settings.searxng_url}/search",
                params={"q": args.query, "format": "json"},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()

        hits: list[SearchHit] = [
            SearchHit(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                published=str(item.get("publishedDate") or ""),
            )
            for item in payload.get("results", [])[: args.max_results]
        ]
        log.info("web_search", query=args.query, n_hits=len(hits))
        return WebSearchResult(query=args.query, hits=hits)
