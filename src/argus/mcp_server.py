"""Expose Argus's tool registry as an MCP server (registry-as-MCP).

The same permission-gated tool registry the agent loop uses (web_search, web_fetch,
rag_search, the sandboxed execute_python) is exposed over the Model Context Protocol
so any MCP host — Claude Desktop, an IDE, another agent — can call Argus's tools.
The bridge is mechanical because the registry already carries everything MCP needs:
each Tool has a name, a docstring description, a Pydantic args model (-> JSON Schema),
and a permission; dispatch() runs it. We list every non-DENY tool and route each
call through the registry's dispatch (so argument validation and error shaping are
shared with the in-process path).

ASK tools (execute_python) are withheld by default and exposed only via
ARGUS_MCP_EXPOSE_ASK, since over MCP the human-in-the-loop approval is the host's
responsibility (the host prompts before any tool call) rather than the loop's.
"""

from __future__ import annotations

from typing import Any

import mcp.types as types
import orjson
from mcp.server import Server
from pydantic import BaseModel

from argus.builders import build_registry
from argus.config import get_settings
from argus.logging import get_logger
from argus.tools.registry import Permission, ToolCall, ToolRegistry

log = get_logger(__name__)


def _exposed(registry: ToolRegistry, *, expose_ask: bool) -> list[str]:
    names: list[str] = []
    for name in registry.names():
        tool = registry.get(name)
        if tool is None or tool.permission is Permission.DENY:
            continue
        if tool.permission is Permission.ASK and not expose_ask:
            continue
        names.append(name)
    return names


def _serialize(content: Any) -> str:
    if isinstance(content, BaseModel):
        return content.model_dump_json()
    return orjson.dumps(content, default=str).decode()


def build_mcp_server(registry: ToolRegistry, *, expose_ask: bool = False) -> Server[Any, Any]:
    server: Server[Any, Any] = Server("argus")
    exposed: list[str] = _exposed(registry, expose_ask=expose_ask)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        tools: list[types.Tool] = []
        for name in exposed:
            tool = registry.get(name)
            if tool is None:
                continue
            tools.append(
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.args_model.model_json_schema(),
                )
            )
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        if name not in exposed:
            # Don't dispatch a hidden (DENY, or ASK-without-the-flag) tool even if a
            # client asks for it by name.
            raise ValueError(f"tool not available: {name!r}")
        # Over MCP the host owns approval, so ASK tools are auto-approved at this seam.
        result = await registry.dispatch(
            ToolCall(name=name, arguments=arguments), approver=_always_approve
        )
        if not result.ok:
            raise ValueError(result.error or "tool failed")
        return [types.TextContent(type="text", text=_serialize(result.content))]

    log.info("mcp_server_built", tools=exposed)
    return server


async def _always_approve(_: ToolCall) -> bool:
    return True


async def run_stdio() -> None:
    # stdio transport: the MCP host launches `argus mcp` as a subprocess and speaks
    # JSON-RPC over stdin/stdout. This is the transport Claude Desktop and most IDE
    # hosts use for a local server.
    from mcp.server.stdio import stdio_server

    settings = get_settings()
    registry = build_registry()
    server = build_mcp_server(registry, expose_ask=settings.mcp_expose_ask)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
