"""LiteLLM gateway wrapper returning normalized, cost-attributed responses."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import litellm
from pydantic import BaseModel

from argus.logging import get_logger

log = get_logger(__name__)

_Structured = TypeVar("_Structured", bound=BaseModel)

TokenSink = Callable[[str], Awaitable[None]]


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
    def __init__(
        self,
        *,
        model: str,
        timeout_s: float,
        temperature: float | None = None,
        num_retries: int = 2,
        fallbacks: list[str] | None = None,
    ) -> None:
        self._model: str = model
        self._timeout: float = timeout_s
        self._temperature: float | None = temperature
        # litellm retries transient failures (timeouts, rate limits, 5xx) with
        # backoff, so a one-off API hiccup never surfaces to the user.
        self._num_retries: int = num_retries
        # If the primary model still fails after its retries, litellm tries each
        # fallback model in order — provider/model degradation never hard-fails.
        self._fallbacks: list[str] | None = fallbacks or None

    def _reliability_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "timeout": self._timeout,
            "num_retries": self._num_retries,
        }
        if self._fallbacks is not None:
            kwargs["fallbacks"] = self._fallbacks
        return kwargs

    def _sampling_kwargs(self) -> dict[str, Any]:
        return {} if self._temperature is None else {"temperature": self._temperature}

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        on_token: TokenSink | None = None,
    ) -> LLMResponse:
        if on_token is None:
            response: Any = await litellm.acompletion(
                model=self._model,
                messages=messages,
                tools=tools,
                **self._reliability_kwargs(),
                **self._sampling_kwargs(),
            )
        else:
            response = await self._stream(messages, tools, on_token)
        return self._normalize(response)

    async def _stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        on_token: TokenSink,
    ) -> Any:
        chunks: list[Any] = []
        stream: Any = await litellm.acompletion(
            model=self._model,
            messages=messages,
            tools=tools,
            **self._reliability_kwargs(),
            stream=True,
            stream_options={"include_usage": True},
            **self._sampling_kwargs(),
        )
        async for chunk in stream:
            chunks.append(chunk)
            choices: Any = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta: str | None = getattr(choices[0].delta, "content", None)
            if delta:
                await on_token(delta)
        return litellm.stream_chunk_builder(chunks, messages=messages)

    def _normalize(self, response: Any) -> LLMResponse:
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
            **self._reliability_kwargs(),
            **self._sampling_kwargs(),
        )
        content: str = response.choices[0].message.content or "{}"
        return schema.model_validate_json(content)
