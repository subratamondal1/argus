from __future__ import annotations

import pytest

from argus.config import Settings


def test_defaults() -> None:
    settings = Settings()
    assert settings.model.startswith("anthropic/")
    assert settings.max_turns > 0
    assert settings.max_cost_usd > 0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_MODEL", "openai/gpt-5")
    monkeypatch.setenv("ARGUS_MAX_TURNS", "3")
    settings = Settings()
    assert settings.model == "openai/gpt-5"
    assert settings.max_turns == 3
