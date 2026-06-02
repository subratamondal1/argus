"""Heading-aware structural chunking of Markdown into <=512-token pieces.

A chunk is a heading-delimited section. Sections that exceed the budget are
split on paragraph boundaries and re-grounded with their heading breadcrumb, so
every chunk stays self-contained for retrieval. Token counts are estimated from
character length (no tokenizer dependency); 512 keeps chunks under the embedder
and reranker input limits.
"""

from __future__ import annotations

import re

MAX_CHUNK_TOKENS: int = 512
_CHARS_PER_TOKEN: int = 4
_HEADING: re.Pattern[str] = re.compile(r"^(#{1,6})\s+(.*)$")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _max_chars(max_tokens: int) -> int:
    return max_tokens * _CHARS_PER_TOKEN


def chunk_markdown(markdown: str, *, max_tokens: int = MAX_CHUNK_TOKENS) -> list[str]:
    chunks: list[str] = []
    for breadcrumb, block in _split_units(markdown):
        if _estimate_tokens(block) <= max_tokens:
            chunks.append(block)
        else:
            chunks.extend(_split_block(breadcrumb, block, max_tokens))
    return [chunk for chunk in chunks if chunk.strip()]


def _split_units(markdown: str) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    current: list[str] = []
    breadcrumb: str = ""

    def flush() -> None:
        nonlocal current
        block: str = "\n".join(current).strip()
        if block:
            units.append((breadcrumb, block))
        current = []

    for line in markdown.splitlines():
        match: re.Match[str] | None = _HEADING.match(line)
        if match is not None:
            flush()
            level: int = len(match.group(1))
            title: str = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            breadcrumb = " > ".join(text for _, text in stack)
        current.append(line)
    flush()
    return units


def _split_block(breadcrumb: str, block: str, max_tokens: int) -> list[str]:
    paragraphs: list[str] = [p for p in re.split(r"\n\s*\n", block) if p.strip()]
    out: list[str] = []
    buffer: list[str] = []
    for paragraph in paragraphs:
        for piece in _hard_split(paragraph, max_tokens):
            candidate: str = "\n\n".join([*buffer, piece])
            if buffer and _estimate_tokens(candidate) > max_tokens:
                out.append(_with_breadcrumb(breadcrumb, "\n\n".join(buffer)))
                buffer = [piece]
            else:
                buffer.append(piece)
    if buffer:
        out.append(_with_breadcrumb(breadcrumb, "\n\n".join(buffer)))
    return out


def _hard_split(paragraph: str, max_tokens: int) -> list[str]:
    limit: int = _max_chars(max_tokens)
    if len(paragraph) <= limit:
        return [paragraph]
    pieces: list[str] = []
    buffer: list[str] = []
    length: int = 0
    for word in paragraph.split():
        if buffer and length + len(word) + 1 > limit:
            pieces.append(" ".join(buffer))
            buffer = [word]
            length = len(word)
        else:
            buffer.append(word)
            length += len(word) + 1
    if buffer:
        pieces.append(" ".join(buffer))
    return pieces


def _with_breadcrumb(breadcrumb: str, text: str) -> str:
    if breadcrumb and not text.lstrip().startswith("#"):
        return f"{breadcrumb}\n\n{text}"
    return text
