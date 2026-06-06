"""LiteLLM gateway wrapper returning normalized, cost-attributed responses."""

from __future__ import annotations

import contextlib
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
        reasoning_effort: str | None = None,
    ) -> None:
        self._model: str = model
        self._timeout: float = timeout_s
        self._temperature: float | None = temperature
        self._reasoning_effort: str | None = reasoning_effort
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

    def _sampling_kwargs(self, *, structured: bool = False) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        # A local Ollama Qwen3.x model silently ignores the JSON-schema constraint when
        # thinking is disabled (think:false) and emits free-form/YAML text, so a structured
        # call keeps the model's default reasoning to actually get schema-valid JSON.
        if self._reasoning_effort is not None and not structured:
            kwargs["reasoning_effort"] = self._reasoning_effort
        return kwargs

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Anthropic caches the large static prefix (tools + system, which precede
        # the conversation) when a cache_control breakpoint is set on the system
        # block — turns 2..N of a loop then reuse it at ~10% of the input cost.
        # OpenAI and the rest cache automatically and ignore the marker, so only
        # rewrite for Anthropic models to avoid sending it where it's unneeded.
        if "anthropic" not in self._model and "claude" not in self._model:
            return messages
        prepared: list[dict[str, Any]] = []
        marked = False
        for message in messages:
            content = message.get("content")
            if not marked and message.get("role") == "system" and isinstance(content, str):
                prepared.append(
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": content,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                )
                marked = True
            else:
                prepared.append(message)
        return prepared

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        on_token: TokenSink | None = None,
    ) -> LLMResponse:
        messages = self._prepare_messages(messages)
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
        try:
            async for chunk in stream:
                chunks.append(chunk)
                choices: Any = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta: str | None = getattr(choices[0].delta, "content", None)
                if delta:
                    await on_token(delta)
            return litellm.stream_chunk_builder(chunks, messages=messages)
        finally:
            # If the client disconnected, the run task is cancelled here — tear the
            # upstream LLM stream down so it stops generating (and billing) instead
            # of running on until the budget/timeout fires.
            aclose = getattr(stream, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()

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
            # Surface it: an uncosted call silently reports $0 and undercounts the
            # budget, so a model LiteLLM can't price should be visible, not hidden.
            log.warning("cost_calc_failed", model=self._model, error=str(error))
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
        messages = self._prepare_messages(messages)
        response: Any = await litellm.acompletion(
            model=self._model,
            messages=messages,
            response_format=schema,
            **self._reliability_kwargs(),
            **self._sampling_kwargs(structured=True),
        )
        content: str = response.choices[0].message.content or "{}"
        return schema.model_validate_json(content)
