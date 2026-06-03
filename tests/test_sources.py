from __future__ import annotations

from argus.agent.sources import Source, dedupe, numbered_payload, sources_from_result
from argus.rag.retriever import RetrievedChunk
from argus.tools.rag_search import RagSearchResult
from argus.tools.registry import ToolResult
from argus.tools.web_fetch import WebFetchResult
from argus.tools.web_search import SearchHit, WebSearchResult


def test_web_search_result_maps_each_hit_to_a_web_source() -> None:
    result = ToolResult(
        name="web_search",
        ok=True,
        content=WebSearchResult(
            query="q",
            hits=[
                SearchHit(title="A", url="https://a.test", snippet="alpha  snippet"),
                SearchHit(title="B", url="https://b.test", snippet="beta"),
            ],
        ),
    )
    sources = sources_from_result(result)

    assert [source.url for source in sources] == ["https://a.test", "https://b.test"]
    assert all(source.origin == "web" for source in sources)
    assert sources[0].snippet == "alpha snippet"


def test_rag_result_carries_origin_doc_and_score() -> None:
    result = ToolResult(
        name="rag_search",
        ok=True,
        content=RagSearchResult(
            query="q",
            chunks=[RetrievedChunk(content="body", source_uri="doc://x", score=0.8123)],
        ),
    )
    sources = sources_from_result(result)

    assert sources[0].origin == "doc"
    assert sources[0].url == "doc://x"
    assert sources[0].score == 0.812


def test_failed_or_unknown_result_yields_no_sources() -> None:
    assert sources_from_result(ToolResult(name="web_fetch", ok=False, error="boom")) == []
    assert sources_from_result(ToolResult(name="other", ok=True, content={"x": 1})) == []


def test_web_fetch_result_yields_single_source() -> None:
    result = ToolResult(
        name="web_fetch",
        ok=True,
        content=WebFetchResult(url="https://c.test", text="long body text", truncated=False),
    )
    sources = sources_from_result(result)

    assert len(sources) == 1
    assert sources[0].url == "https://c.test"


def test_dedupe_keeps_first_occurrence_by_url() -> None:
    sources = [
        Source(title="A1", url="https://a.test", snippet="s1", origin="web"),
        Source(title="A2", url="https://a.test", snippet="s2", origin="web"),
        Source(title="B", url="https://b.test", snippet="s3", origin="web"),
    ]
    unique = dedupe(sources)

    assert [source.title for source in unique] == ["A1", "B"]


def test_numbered_payload_assigns_one_based_ids() -> None:
    sources = [
        Source(title="A", url="https://a.test", snippet="s", origin="web"),
        Source(title="B", url="https://b.test", snippet="s", origin="doc", score=0.5),
    ]
    payload = numbered_payload(sources)

    assert [item["id"] for item in payload] == [1, 2]
    assert payload[0]["origin"] == "web"
    assert payload[1]["score"] == 0.5
