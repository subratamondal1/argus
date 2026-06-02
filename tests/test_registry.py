from __future__ import annotations

import pytest
from pydantic import BaseModel

from argus.tools.registry import Permission, ToolCall, ToolRegistry


class EchoArgs(BaseModel):
    text: str


def make_registry(permission: Permission = Permission.ALLOW) -> ToolRegistry:
    registry = ToolRegistry()

    @registry.tool(permission=permission)
    async def echo(args: EchoArgs) -> dict[str, str]:
        """Echo the text back."""
        return {"echo": args.text}

    return registry


def test_schema_is_derived_from_args_model() -> None:
    schema = make_registry().schema()
    assert len(schema) == 1
    function = schema[0]["function"]
    assert function["name"] == "echo"
    assert "Echo the text back." in function["description"]
    assert "text" in function["parameters"]["properties"]


async def test_dispatch_ok() -> None:
    result = await make_registry().dispatch(ToolCall(name="echo", arguments={"text": "hi"}))
    assert result.ok
    assert result.content == {"echo": "hi"}


async def test_unknown_tool() -> None:
    result = await make_registry().dispatch(ToolCall(name="nope", arguments={}))
    assert not result.ok
    assert "unknown" in (result.error or "")


async def test_invalid_arguments() -> None:
    result = await make_registry().dispatch(ToolCall(name="echo", arguments={"wrong": 1}))
    assert not result.ok
    assert "invalid arguments" in (result.error or "")


async def test_permission_deny_blocks() -> None:
    result = await make_registry(Permission.DENY).dispatch(
        ToolCall(name="echo", arguments={"text": "hi"})
    )
    assert not result.ok
    assert "denied" in (result.error or "")


async def test_permission_ask_defaults_to_deny() -> None:
    result = await make_registry(Permission.ASK).dispatch(
        ToolCall(name="echo", arguments={"text": "hi"})
    )
    assert not result.ok


async def test_permission_ask_runs_when_approved() -> None:
    async def approve(_call: ToolCall) -> bool:
        return True

    result = await make_registry(Permission.ASK).dispatch(
        ToolCall(name="echo", arguments={"text": "hi"}), approver=approve
    )
    assert result.ok


def test_tool_without_docstring_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="docstring"):

        @registry.tool()
        async def no_doc(args: EchoArgs) -> dict[str, str]:
            return {}
