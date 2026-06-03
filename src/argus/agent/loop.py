"""The hand-written agent loop: an LLM in a tool-use loop, framework-free."""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Protocol

import orjson
from pydantic import BaseModel

from argus.agent.budget import Budget, BudgetState, BudgetStop
from argus.agent.events import EventSink, emit
from argus.agent.sources import Source, sources_from_result
from argus.llm import LLMResponse, TokenSink
from argus.logging import get_logger
from argus.tools.registry import Approver, ToolCall, ToolRegistry, ToolResult

log = get_logger(__name__)


class CompletionClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        on_token: TokenSink | None = None,
    ) -> LLMResponse: ...


@dataclass(frozen=True)
class AgentResult:
    answer: str
    stop_reason: str
    turns: int
    tokens: int
    cost_usd: float
    transcript: list[dict[str, Any]]
    sources: list[Source] = field(default_factory=list)


def _result_to_text(result: ToolResult) -> str:
    if not result.ok:
        return orjson.dumps({"error": result.error}).decode()
    content: Any = result.content
    if isinstance(content, BaseModel):
        return content.model_dump_json()
    if isinstance(content, str):
        return content
    return orjson.dumps(content, default=str).decode()


def _parse_arguments(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded: Any = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


class AgentLoop:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        llm: CompletionClient,
        budget: Budget,
        system_prompt: str,
        approver: Approver | None = None,
    ) -> None:
        self._registry: ToolRegistry = registry
        self._llm: CompletionClient = llm
        self._budget: Budget = budget
        self._system_prompt: str = system_prompt
        self._approver: Approver | None = approver

    async def run(
        self,
        user_input: str,
        *,
        on_event: EventSink | None = None,
        stream_tokens: bool = False,
    ) -> AgentResult:
        state: BudgetState = BudgetState(self._budget)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_input},
        ]
        tools: list[dict[str, Any]] | None = self._registry.schema() or None
        answer: str = ""
        stop_reason: str = "completed"
        collected: list[Source] = []

        token_sink: TokenSink | None = None
        if stream_tokens and on_event is not None:

            async def token_sink(delta: str) -> None:
                await emit(on_event, "token", text=delta)

        async with AsyncExitStack() as stack:
            stack.callback(lambda: log.debug("agent_loop_teardown", turns=state.turns))

            while True:
                stop: BudgetStop | None = state.exceeded()
                if stop is not None:
                    stop_reason = stop.value
                    answer = answer or f"[stopped: {stop.value} budget reached]"
                    break

                response: LLMResponse = await self._llm.complete(
                    messages, tools=tools, on_token=token_sink
                )
                state.record_turn(
                    tokens=response.prompt_tokens + response.completion_tokens,
                    cost_usd=response.cost_usd,
                )
                log.info(
                    "turn",
                    n=state.turns,
                    tokens=state.tokens,
                    cost_usd=round(state.cost_usd, 4),
                    tool_calls=len(response.tool_calls),
                )
                await emit(
                    on_event,
                    "turn",
                    n=state.turns,
                    tool_calls=len(response.tool_calls),
                    cost_usd=round(state.cost_usd, 4),
                )

                if not response.tool_calls:
                    answer = response.content or ""
                    stop_reason = "completed"
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {"name": call.name, "arguments": call.arguments},
                            }
                            for call in response.tool_calls
                        ],
                    }
                )

                for call in response.tool_calls:
                    result: ToolResult = await self._registry.dispatch(
                        ToolCall(name=call.name, arguments=_parse_arguments(call.arguments)),
                        approver=self._approver,
                    )
                    collected.extend(sources_from_result(result))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": _result_to_text(result),
                        }
                    )

        return AgentResult(
            answer=answer,
            stop_reason=stop_reason,
            turns=state.turns,
            tokens=state.tokens,
            cost_usd=round(state.cost_usd, 6),
            transcript=messages,
            sources=collected,
        )
