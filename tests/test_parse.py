from __future__ import annotations

from pathlib import Path

import pytest

from argus.rag import parse as parse_mod
from argus.rag.parse import _is_url, _parse_pdf, parse_source


def test_pdf_with_text_skips_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def ocr_must_not_run(path: Path) -> str:
        raise AssertionError("OCR fallback must not run when pypdf extracts text")

    monkeypatch.setattr(parse_mod, "_parse_pdf_pypdf", lambda path: "real extracted text")
    monkeypatch.setattr(parse_mod, "_parse_pdf_ocr", ocr_must_not_run)
    assert _parse_pdf(tmp_path / "doc.pdf") == "real extracted text"


def test_scanned_pdf_falls_back_to_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parse_mod, "_parse_pdf_pypdf", lambda path: "   \n  ")  # no text layer
    monkeypatch.setattr(parse_mod, "_parse_pdf_ocr", lambda path: "OCR-RECOVERED TEXT")
    assert _parse_pdf(tmp_path / "scan.pdf") == "OCR-RECOVERED TEXT"


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
