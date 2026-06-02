"""Contextual Retrieval: a short LLM-written prefix situating each chunk.

Following Anthropic's Contextual Retrieval, each chunk is prepended with one or
two sentences that place it within the whole document before it is embedded and
lexically indexed. This is the highest-leverage retrieval-quality upgrade, and on
the local LLM path it is effectively free (compute-only, at ingest time).
"""

from __future__ import annotations

from argus.llm import LLMClient

_MAX_DOC_CHARS: int = 12000

_SYSTEM: str = (
    "You situate a chunk of a document within the whole document for search "
    "retrieval. Reply with one or two short sentences of context only — no "
    "preamble, no quotes, nothing else."
)


def context_messages(document: str, chunk: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"<document>\n{document[:_MAX_DOC_CHARS]}\n</document>\n\n"
                f"<chunk>\n{chunk}\n</chunk>\n\n"
                "Give the short context that situates this chunk within the document."
            ),
        },
    ]


async def contextualize(llm: LLMClient, *, document: str, chunk: str) -> str:
    response = await llm.complete(context_messages(document, chunk))
    return (response.content or "").strip()
