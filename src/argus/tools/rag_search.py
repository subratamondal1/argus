"""The rag_search tool: retrieve from the local ingested-document corpus."""

from __future__ import annotations

from pydantic import BaseModel, Field

from argus.logging import get_logger
from argus.rag.retriever import RetrievedChunk, retrieve
from argus.tools.registry import Permission, ToolRegistry

log = get_logger(__name__)


class RagSearchArgs(BaseModel):
    query: str = Field(description="What to look up in the ingested documents.")
    top_k: int = Field(default=5, ge=1, le=20, description="How many chunks to return.")


class RagSearchResult(BaseModel):
    query: str = Field(description="The query that produced these chunks.")
    chunks: list[RetrievedChunk] = Field(description="Retrieved chunks in fused-rank order.")


def register_rag_search(registry: ToolRegistry, *, corpus: str = "default") -> None:
    @registry.tool(permission=Permission.ALLOW)
    async def rag_search(args: RagSearchArgs) -> RagSearchResult:
        """Search the documents ingested into Argus's local corpus.

        Use this for questions about that ingested, internal knowledge. Prefer
        web_search for current events and live facts; you may call both and
        reconcile. Each result carries its source_uri so you can cite it.
        """
        chunks: list[RetrievedChunk] = await retrieve(args.query, top_k=args.top_k, corpus=corpus)
        log.info("rag_search", query=args.query, n_chunks=len(chunks))
        return RagSearchResult(query=args.query, chunks=chunks)
