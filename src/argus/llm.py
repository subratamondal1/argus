"""LiteLLM gateway wrapper returning normalized, cost-attributed responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

import litellm
from pydantic import BaseModel

from argus.logging import get_logger

log = get_logger(__name__)

_Structured = TypeVar("_Structured", bound=BaseModel)


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class LLMClient:
    def __init__(self, *, model: str, timeout_s: float) -> None:
        self._model: str = model
        self._timeout: float = timeout_s

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        response: Any = await litellm.acompletion(
            model=self._model,
            messages=messages,
            tools=tools,
            timeout=self._timeout,
        )

        message: Any = response.choices[0].message
        tool_calls: list[ToolCallRequest] = [
            ToolCallRequest(id=call.id, name=call.function.name, arguments=call.function.arguments)
            for call in (message.tool_calls or [])
        ]
        usage: Any = response.usage
        prompt_tokens: int = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens: int = int(getattr(usage, "completion_tokens", 0) or 0)

        try:
            cost_usd: float = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception as error:
            log.debug("cost_calc_failed", error=str(error))
            cost_usd = 0.0

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type[_Structured]
    ) -> _Structured:
        response: Any = await litellm.acompletion(
            model=self._model,
            messages=messages,
            response_format=schema,
            timeout=self._timeout,
        )
        content: str = response.choices[0].message.content or "{}"
        return schema.model_validate_json(content)
