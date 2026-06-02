from __future__ import annotations

from argus.rag.chunking import chunk_markdown


def test_each_section_is_its_own_chunk() -> None:
    markdown = "# A\n\nalpha body\n\n## B\n\nbeta body"
    chunks = chunk_markdown(markdown)
    assert len(chunks) == 2
    assert chunks[0].startswith("# A")
    assert chunks[1].startswith("## B")


def test_preamble_before_first_heading_is_kept() -> None:
    markdown = "intro paragraph\n\n# Section\n\nbody"
    chunks = chunk_markdown(markdown)
    assert any("intro paragraph" in chunk for chunk in chunks)


def test_long_section_splits_under_budget_and_regrounds() -> None:
    paragraphs = "\n\n".join(f"paragraph number {i} " + "lorem ipsum " * 20 for i in range(12))
    markdown = f"## Deep Dive\n\n{paragraphs}"
    chunks = chunk_markdown(markdown, max_tokens=128)

    assert len(chunks) > 1
    assert all(len(chunk) <= 128 * 4 + len("Deep Dive") + 4 for chunk in chunks)
    # the first chunk carries the heading; later chunks are re-grounded with the breadcrumb
    assert chunks[0].startswith("## Deep Dive")
    assert all("Deep Dive" in chunk for chunk in chunks[1:])


def test_empty_input_yields_no_chunks() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("\n\n   \n") == []
