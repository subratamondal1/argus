# ruff: noqa: I001
from __future__ import annotations

import pytest

pytest.importorskip("mcp")  # the mcp extra is optional; skip without it


def test_exposed_excludes_deny_and_gates_ask() -> None:
    from argus.builders import build_registry
    from argus.mcp_server import _exposed

    registry = build_registry()
    default = _exposed(registry, expose_ask=False)
    assert {"web_search", "web_fetch", "rag_search"} <= set(default)
    assert "execute_python" not in default  # ASK tool withheld by default
    assert "execute_python" in _exposed(registry, expose_ask=True)


def test_serialize_handles_pydantic_and_plain() -> None:
    from argus.mcp_server import _serialize
    from argus.tools.web_search import SearchHit, WebSearchResult

    result = WebSearchResult(query="q", hits=[SearchHit(title="t", url="http://x", snippet="s")])
    assert '"query":"q"' in _serialize(result)
    assert _serialize({"a": 1}) == '{"a":1}'


async def test_mcp_protocol_lists_and_gates_tools() -> None:
    # fmt: off
    from mcp.shared.memory import create_connected_server_and_client_session as connect  # ty: ignore[unresolved-import]
    # fmt: on
    from argus.builders import build_registry
    from argus.mcp_server import build_mcp_server

    server = build_mcp_server(build_registry(), expose_ask=False)
    async with connect(server) as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        assert {"web_search", "web_fetch", "rag_search"} <= names
        assert "execute_python" not in names  # not advertised
        # And a client asking for the withheld tool by name is rejected, not dispatched.
        rejected = await client.call_tool("execute_python", {"code": "print(1)"})
        assert rejected.isError
