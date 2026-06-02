from __future__ import annotations

import pytest

from argus.config import Settings


def test_default_model_is_anthropic() -> None:
    assert str(Settings.model_fields["model"].default).startswith("anthropic/")


def test_default_budget_is_positive() -> None:
    assert Settings.model_fields["max_turns"].default > 0
    assert Settings.model_fields["max_cost_usd"].default > 0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_MODEL", "openai/gpt-5")
    monkeypatch.setenv("ARGUS_MAX_TURNS", "3")
    settings = Settings()
    assert settings.model == "openai/gpt-5"
    assert settings.max_turns == 3


def test_searxng_url_composed_from_host_and_port() -> None:
    settings = Settings(searxng_host="localhost", searxng_port=8085)
    assert settings.searxng_url == "http://localhost:8085"


def test_rag_defaults() -> None:
    assert str(Settings.model_fields["database_url"].default).startswith("postgresql://")
    assert str(Settings.model_fields["embedding_model"].default).startswith("ollama/")
    assert Settings.model_fields["rag_enabled"].default is True
    assert Settings.model_fields["rerank_enabled"].default is False
