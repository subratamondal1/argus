"""Turn a path or URL into Markdown for chunking.

URLs and local HTML go through trafilatura; plain-text/Markdown files are read
as-is; PDF/DOCX/PPTX go through docling — an optional, lazily-imported extra so
the default install stays light. Local-file reads run off the event loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx
import trafilatura

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)

_USER_AGENT: str = (
    "Mozilla/5.0 (compatible; ArgusResearch/0.1; +https://github.com/subratamondal1/argus)"
)
_TEXT_SUFFIXES: frozenset[str] = frozenset({".md", ".markdown", ".txt", ".rst"})
_HTML_SUFFIXES: frozenset[str] = frozenset({".html", ".htm"})
_DOCLING_SUFFIXES: frozenset[str] = frozenset({".pdf", ".docx", ".pptx"})


@dataclass(frozen=True)
class ParsedDoc:
    uri: str
    markdown: str


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _html_to_markdown(raw: str) -> str:
    extracted: str | None = trafilatura.extract(
        raw, output_format="markdown", include_comments=False
    )
    return (extracted or "").strip()


async def parse_source(source: str) -> ParsedDoc:
    if _is_url(source):
        return await _parse_url(source)
    return await asyncio.to_thread(_parse_file, source)


def _parse_file(source: str) -> ParsedDoc:
    path: Path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {source}")
    suffix: str = path.suffix.lower()
    if suffix in _HTML_SUFFIXES:
        return ParsedDoc(
            uri=str(path), markdown=_html_to_markdown(path.read_text(encoding="utf-8"))
        )
    if suffix in _DOCLING_SUFFIXES:
        return ParsedDoc(uri=str(path), markdown=_parse_with_docling(path))
    return ParsedDoc(uri=str(path), markdown=path.read_text(encoding="utf-8"))


async def _parse_url(url: str) -> ParsedDoc:
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_s,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        response: httpx.Response = await client.get(url)
        response.raise_for_status()
    markdown: str = _html_to_markdown(response.text)
    log.info("parse_url", url=url, chars=len(markdown))
    return ParsedDoc(uri=url, markdown=markdown)


def _parse_with_docling(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter  # ty: ignore[unresolved-import]
    except ModuleNotFoundError as error:
        raise RuntimeError(
            f"parsing {path.suffix} files needs the 'parse' extra: uv sync --extra parse"
        ) from error
    converter = DocumentConverter()
    result = converter.convert(str(path))
    markdown: str = result.document.export_to_markdown()
    log.info("parse_docling", path=str(path), chars=len(markdown))
    return markdown
