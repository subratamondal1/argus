from __future__ import annotations

from argus.llm import LLMClient


def test_sampling_kwargs_omits_temperature_by_default() -> None:
    client = LLMClient(model="openai/gpt-5.4-mini", timeout_s=30.0)
    assert client._sampling_kwargs() == {}


def test_sampling_kwargs_pins_temperature_when_set() -> None:
    judge = LLMClient(model="openai/gpt-5.4-mini", timeout_s=30.0, temperature=0.0)
    assert judge._sampling_kwargs() == {"temperature": 0.0}
