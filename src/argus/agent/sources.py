"""Structured sources captured from tool results, for inline citation.

A research answer is only trustworthy if every claim points back to where it
came from. The searcher loops call web_search / web_fetch / rag_search; this
module turns those raw tool results into one uniform Source the UI can render
as a citation card. The orchestrator numbers the deduplicated set [1..N] and
the synthesizer cites them inline as [N], so a hovered citation resolves to the
exact card it rests on.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from argus.tools.rag_search import RagSearchResult
from argus.tools.registry import ToolResult
from argus.tools.web_fetch import WebFetchResult
from argus.tools.web_search import WebSearchResult

_SNIPPET_CHARS: int = 240


class Source(BaseModel):
    title: str = Field(description="Human-readable title or document name.")
    url: str = Field(description="Public URL or source_uri the claim can be traced back to.")
    snippet: str = Field(description="Short excerpt that supports the citing claim.")
    origin: str = Field(description="'web' for live web results, 'doc' for the ingested corpus.")
    score: float | None = Field(
        default=None, description="Relevance score when the source carries one (RAG); else null."
    )


def _clip(text: str) -> str:
    flat: str = " ".join(text.split())
    if len(flat) <= _SNIPPET_CHARS:
        return flat
    return flat[: _SNIPPET_CHARS - 1].rstrip() + "…"


def sources_from_result(result: ToolResult) -> list[Source]:
    if not result.ok or result.content is None:
        return []
    content: object = result.content
    if isinstance(content, WebSearchResult):
        return [
            Source(
                title=hit.title or hit.url,
                url=hit.url,
                snippet=_clip(hit.snippet),
                origin="web",
            )
            for hit in content.hits
            if hit.url
        ]
    if isinstance(content, WebFetchResult):
        return [
            Source(title=content.url, url=content.url, snippet=_clip(content.text), origin="web")
        ]
    if isinstance(content, RagSearchResult):
        return [
            Source(
                title=chunk.source_uri,
                url=chunk.source_uri,
                snippet=_clip(chunk.content),
                origin="doc",
                score=round(chunk.score, 3),
            )
            for chunk in content.chunks
        ]
    return []


def dedupe(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    unique: list[Source] = []
    for source in sources:
        if source.url in seen:
            continue
        seen.add(source.url)
        unique.append(source)
    return unique


def numbered_payload(sources: list[Source]) -> list[dict[str, object]]:
    return [{"id": index + 1, **source.model_dump()} for index, source in enumerate(sources)]
