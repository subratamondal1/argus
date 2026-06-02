from __future__ import annotations

from pathlib import Path

import pytest

from argus.rag.parse import _is_url, parse_source


def test_url_detection() -> None:
    assert _is_url("https://example.com")
    assert _is_url("http://example.com")
    assert not _is_url("/tmp/doc.md")
    assert not _is_url("doc.md")


async def test_parses_local_markdown(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# Title\n\nbody text", encoding="utf-8")
    parsed = await parse_source(str(doc))
    assert parsed.uri == str(doc)
    assert "Title" in parsed.markdown


async def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await parse_source(str(tmp_path / "nope.md"))
