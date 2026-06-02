"""Self-registering tool registry with permission gating and async dispatch."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, get_type_hints

from pydantic import BaseModel, ValidationError


class Permission(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class ToolFunction(Protocol):
    __name__: str

    async def __call__(self, args: Any, /) -> Any: ...


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    content: Any = None
    error: str | None = None


Approver = Callable[[ToolCall], Awaitable[bool]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    func: ToolFunction
    permission: Permission

    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


def _extract_args_model(func: ToolFunction) -> type[BaseModel]:
    parameters: list[inspect.Parameter] = [
        parameter
        for parameter in inspect.signature(func).parameters.values()
        if parameter.name != "self"
    ]
    if len(parameters) != 1:
        raise ValueError(f"tool {func.__name__!r} must take exactly one Pydantic-model argument")
    annotation: Any = get_type_hints(func).get(parameters[0].name)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    raise ValueError(f"tool {func.__name__!r} argument must be annotated with a BaseModel subclass")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def tool(
        self, *, permission: Permission = Permission.ALLOW
    ) -> Callable[[ToolFunction], ToolFunction]:
        def decorator(func: ToolFunction) -> ToolFunction:
            description: str | None = inspect.getdoc(func)
            if not description:
                raise ValueError(
                    f"tool {func.__name__!r} needs a docstring; it becomes the LLM description"
                )
            self._tools[func.__name__] = Tool(
                name=func.__name__,
                description=description,
                args_model=_extract_args_model(func),
                func=func,
                permission=permission,
            )
            return func

        return decorator

    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schema(self) -> list[dict[str, Any]]:
        return [tool.json_schema() for tool in self._tools.values()]

    async def dispatch(self, call: ToolCall, *, approver: Approver | None = None) -> ToolResult:
        tool: Tool | None = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.name, ok=False, error=f"unknown tool: {call.name!r}")

        if tool.permission is Permission.DENY:
            return ToolResult(call.name, ok=False, error="denied by policy")
        if tool.permission is Permission.ASK:
            is_approved: bool = await approver(call) if approver is not None else False
            if not is_approved:
                return ToolResult(call.name, ok=False, error="denied (no approval granted)")

        try:
            args: BaseModel = tool.args_model.model_validate(call.arguments)
        except ValidationError as error:
            return ToolResult(call.name, ok=False, error=f"invalid arguments: {error}")

        try:
            content: Any = await tool.func(args)
        except Exception as error:
            return ToolResult(call.name, ok=False, error=f"{type(error).__name__}: {error}")

        return ToolResult(call.name, ok=True, content=content)
