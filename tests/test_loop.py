from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.llm import LLMResponse, ToolCallRequest
from argus.tools.registry import ToolRegistry


class EchoArgs(BaseModel):
    text: str


class FakeLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses: list[LLMResponse] = list(responses)
        self.calls: int = 0

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        return self._responses.pop(0)


def _registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.tool()
    async def echo(args: EchoArgs) -> dict[str, str]:
        """Echo the text back."""
        return {"echo": args.text}

    return registry


def _generous_budget(max_turns: int = 10) -> Budget:
    return Budget(max_turns=max_turns, max_tokens=10**6, max_wallclock_s=60.0, max_cost_usd=10.0)


def _tool_turn() -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCallRequest(id="c1", name="echo", arguments='{"text": "hi"}')],
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.01,
    )


async def test_loop_calls_tool_then_answers() -> None:
    llm = FakeLLM(
        [
            _tool_turn(),
            LLMResponse(
                content="the answer",
                tool_calls=[],
                prompt_tokens=8,
                completion_tokens=4,
                cost_usd=0.01,
            ),
        ]
    )
    loop = AgentLoop(
        registry=_registry_with_echo(),
        llm=llm,
        budget=_generous_budget(),
        system_prompt="sys",
    )
    result = await loop.run("question")

    assert result.answer == "the answer"
    assert result.stop_reason == "completed"
    assert result.turns == 2
    assert llm.calls == 2
    assert any(message.get("role") == "tool" for message in result.transcript)


async def test_loop_stops_on_turn_budget() -> None:
    llm = FakeLLM([_tool_turn() for _ in range(10)])
    loop = AgentLoop(
        registry=_registry_with_echo(),
        llm=llm,
        budget=_generous_budget(max_turns=2),
        system_prompt="sys",
    )
    result = await loop.run("question")

    assert result.stop_reason == "max_turns"
    assert result.turns == 2
