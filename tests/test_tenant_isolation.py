from __future__ import annotations

from pathlib import Path

import pytest

from argus.db import close_pool, get_pool
from argus.rag.ingest import ingest_source
from argus.rag.retriever import retrieve

pytestmark = pytest.mark.integration

_CORPUS: str = "tenant-itest"


@pytest.fixture(autouse=True)
async def _require_ollama() -> None:
    import httpx

    from argus.config import get_settings

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.get(get_settings().ollama_base_url)
    except Exception:
        pytest.skip("Ollama not reachable")


async def _purge() -> None:
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute("DELETE FROM chunks WHERE corpus = $1", _CORPUS)


async def test_retrieval_is_isolated_per_tenant(tmp_path: Path) -> None:
    alpha = tmp_path / "alpha.md"
    alpha.write_text("Alpha Corp roadmap: launch the Quasar product in March.", encoding="utf-8")
    beta = tmp_path / "beta.md"
    beta.write_text("Beta Inc plan: acquire the Nimbus startup in June.", encoding="utf-8")

    try:
        await _purge()
        await ingest_source(str(alpha), corpus=_CORPUS, tenant="alpha")
        await ingest_source(str(beta), corpus=_CORPUS, tenant="beta")

        alpha_hits = await retrieve("product roadmap", corpus=_CORPUS, tenant="alpha")
        beta_hits = await retrieve("acquisition plan", corpus=_CORPUS, tenant="beta")
        alpha_text = " ".join(chunk.content for chunk in alpha_hits)
        beta_text = " ".join(chunk.content for chunk in beta_hits)

        assert "Quasar" in alpha_text and "Nimbus" not in alpha_text
        assert "Nimbus" in beta_text and "Quasar" not in beta_text

        # Even a query aimed at the OTHER tenant's data returns nothing of it.
        leak = await retrieve("Nimbus acquisition", corpus=_CORPUS, tenant="alpha")
        assert all("Nimbus" not in chunk.content for chunk in leak)
    finally:
        await _purge()
        await close_pool()
