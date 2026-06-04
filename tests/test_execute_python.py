from __future__ import annotations

import signal
import sys

import pytest

from argus.tools.execute_python import register_execute_python
from argus.tools.registry import ToolCall, ToolRegistry, ToolResult

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the subprocess sandbox relies on POSIX setsid/killpg/rlimits",
)


async def _approve(_call: ToolCall) -> bool:
    return True


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_execute_python(registry)
    return registry


async def _run(code: str) -> ToolResult:
    return await _registry().dispatch(
        ToolCall(name="execute_python", arguments={"code": code}),
        approver=_approve,
    )


async def test_safe_snippet_returns_stdout() -> None:
    result = await _run("print(6 * 7)")
    assert result.ok
    assert result.content.ok is True
    assert result.content.exit_code == 0
    assert result.content.stdout.strip() == "42"
    assert result.content.timed_out is False


async def test_requires_approval() -> None:
    # No approver -> the ASK gate denies before any process is spawned.
    result = await _registry().dispatch(
        ToolCall(name="execute_python", arguments={"code": "print(1)"})
    )
    assert not result.ok
    assert "denied" in (result.error or "")


async def test_timeout_kills_the_process_group(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.config import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ARGUS_EXEC_TIMEOUT_S", "0.5")
    monkeypatch.setenv("ARGUS_EXEC_CPU_SECONDS", "10")
    assert Settings().exec_timeout_s == 0.5

    result = await _run("import time\nwhile True:\n    time.sleep(0.05)\n")
    get_settings.cache_clear()

    assert result.ok  # dispatch itself succeeded
    assert result.content.ok is False
    assert result.content.timed_out is True
    # killpg(SIGKILL) reaped the runaway loop; asyncio reports a signal death as -signo.
    assert result.content.exit_code == -signal.SIGKILL


async def test_network_access_is_blocked() -> None:
    # The runner preamble neuters socket creation, so the snippet can't reach the network
    # even on a host with egress. This is the in-band best-effort block; the hard guarantee
    # is the production netns + egress-firewall (or microVM/gVisor) layer documented in the
    # module. The test pins the behaviour the tool actually ships: socket() raises.
    code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "    print('CONNECTED')\n"
        "except OSError as e:\n"
        "    print('BLOCKED', e)\n"
    )
    result = await _run(code)
    assert result.ok
    assert "CONNECTED" not in result.content.stdout
    assert "BLOCKED" in result.content.stdout


async def test_oversized_output_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ARGUS_EXEC_MAX_OUTPUT_CHARS", "100")

    result = await _run("print('x' * 5000)")
    get_settings.cache_clear()

    assert result.ok
    assert result.content.truncated is True
    assert len(result.content.stdout) <= 100


async def test_nonzero_exit_is_a_failed_run() -> None:
    result = await _run("raise SystemExit(3)")
    assert result.ok  # the tool ran fine
    assert result.content.ok is False
    assert result.content.exit_code == 3
