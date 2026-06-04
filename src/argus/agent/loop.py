"""The hand-written agent loop: an LLM in a tool-use loop, framework-free."""

from __future__ import annotations

from collections import Counter
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


def _wrap_untrusted(result: ToolResult) -> str:
    # Frame successful tool output as untrusted external data so embedded
    # instructions in a fetched page / ingested doc aren't treated as orders
    # (pairs with the SECURITY clause in the system prompt). Error results are
    # our own text, so they pass through unwrapped.
    text: str = _result_to_text(result)
    if not result.ok:
        return text
    return f"<untrusted_tool_output>\n{text}\n</untrusted_tool_output>"


def _parse_arguments(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded: Any = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# Stop the loop when the SAME (tool, args) call is issued this many times — a
# planner stuck on web_search('same query') otherwise burns the whole budget.
_CYCLE_LIMIT: int = 3


def _call_signature(name: str, args: dict[str, Any]) -> str:
    return orjson.dumps({"n": name, "a": args}, option=orjson.OPT_SORT_KEYS).decode()


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
        seen_calls: Counter[str] = Counter()

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

                cycling: bool = False
                for call in response.tool_calls:
                    parsed: dict[str, Any] = _parse_arguments(call.arguments)
                    seen_calls[_call_signature(call.name, parsed)] += 1
                    result: ToolResult = await self._registry.dispatch(
                        ToolCall(name=call.name, arguments=parsed),
                        approver=self._approver,
                    )
                    collected.extend(sources_from_result(result))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": _wrap_untrusted(result),
                        }
                    )
                    if seen_calls[_call_signature(call.name, parsed)] >= _CYCLE_LIMIT:
                        cycling = True

                if cycling:
                    stop_reason = "cycle"
                    answer = answer or "[stopped: repeated the same tool call — likely a loop]"
                    log.warning("agent_cycle", turns=state.turns)
                    break

        return AgentResult(
            answer=answer,
            stop_reason=stop_reason,
            turns=state.turns,
            tokens=state.tokens,
            cost_usd=round(state.cost_usd, 6),
            transcript=messages,
            sources=collected,
        )
