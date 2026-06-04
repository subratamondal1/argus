from __future__ import annotations

from argus.llm import LLMClient


def test_sampling_kwargs_omits_temperature_by_default() -> None:
    client = LLMClient(model="openai/gpt-5.4-mini", timeout_s=30.0)
    assert client._sampling_kwargs() == {}


def test_sampling_kwargs_pins_temperature_when_set() -> None:
    judge = LLMClient(model="openai/gpt-5.4-mini", timeout_s=30.0, temperature=0.0)
    assert judge._sampling_kwargs() == {"temperature": 0.0}


def test_reliability_kwargs_carries_timeout_and_retries() -> None:
    client = LLMClient(model="openai/gpt-5.4-mini", timeout_s=12.0, num_retries=3)
    kwargs = client._reliability_kwargs()
    assert kwargs["timeout"] == 12.0
    assert kwargs["num_retries"] == 3
    assert "fallbacks" not in kwargs


def test_reliability_kwargs_includes_fallbacks_when_configured() -> None:
    client = LLMClient(
        model="openai/gpt-5.4-mini",
        timeout_s=30.0,
        fallbacks=["anthropic/claude-haiku-4-5"],
    )
    assert client._reliability_kwargs()["fallbacks"] == ["anthropic/claude-haiku-4-5"]


def test_empty_fallbacks_normalize_to_none() -> None:
    client = LLMClient(model="openai/gpt-5.4-mini", timeout_s=30.0, fallbacks=[])
    assert "fallbacks" not in client._reliability_kwargs()


_MESSAGES = [
    {"role": "system", "content": "you are a careful research assistant"},
    {"role": "user", "content": "hello"},
]


def test_non_anthropic_messages_pass_through_unchanged() -> None:
    client = LLMClient(model="openai/gpt-5.4-mini", timeout_s=30.0)
    assert client._prepare_messages(_MESSAGES) == _MESSAGES


def test_anthropic_caches_the_system_prefix() -> None:
    client = LLMClient(model="anthropic/claude-sonnet-4-6", timeout_s=30.0)
    prepared = client._prepare_messages(_MESSAGES)
    system_block = prepared[0]["content"][0]
    assert system_block["text"] == "you are a careful research assistant"
    assert system_block["cache_control"] == {"type": "ephemeral"}
    assert prepared[1] == _MESSAGES[1]  # user message untouched


def test_cache_marker_is_idempotent() -> None:
    client = LLMClient(model="claude-haiku-4-5", timeout_s=30.0)
    once = client._prepare_messages(_MESSAGES)
    twice = client._prepare_messages(once)
    assert twice == once
