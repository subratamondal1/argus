"""The execute_python tool: run a short model-generated Python snippet in a subprocess sandbox.

The agent needs to *compute* — parse a number out of a fetched page, do arithmetic
the LLM gets wrong, transform a small table — not just retrieve. The unsafe shortcut
is to ``exec()`` the model's string in this process: there is no boundary, so an
infinite loop hangs the worker, ``open("/etc/passwd")`` reads host secrets, and
``os.system`` runs anything. RestrictedPython only filters the AST at compile time;
attribute/dunder tricks and C-level escapes have repeatedly defeated it, so it is not
a security boundary for adversarial input — and LLM output is adversarial by definition
(prompt injection turns "write a test" into "exfiltrate the env").

The pragmatic, genuinely-safe answer for a single-user OSS showcase is an OS-process
sandbox: a fresh ``python -I -S -B`` child with NO network, a hard wall-clock timeout
that kills the whole process *group*, CPU + address-space + file-size rlimits applied
in the child before exec, an empty private working directory, and a minimal environment.
The child is its own kernel-scheduled process, so a runaway loop or fork bomb is bounded
by rlimits and the timeout instead of taking down the orchestrator.

The production scale-up path (multi-tenant, hostile input at volume) is a hardware or
user-space kernel boundary — gVisor, a Firecracker microVM, nsjail, or a managed sandbox
like E2B — because a subprocess still shares the host kernel's ~40M-line C attack surface
(one kernel CVE escapes it). See skills/sandboxing-engineering/ for that ladder.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Final

from pydantic import BaseModel, Field

from argus.config import get_settings
from argus.logging import get_logger
from argus.tools.registry import Permission, ToolRegistry

log = get_logger(__name__)

_KILL_GRACE_S: Final[float] = 0.5

# Best-effort, in-band network block: neuter socket creation before the snippet runs so the
# common cases (socket / urllib / http.client / requests) raise instead of reaching the network.
# This is DEFENSE IN DEPTH, NOT the guarantee — a subprocess inherits the host network namespace,
# so the real no-network boundary is a netns + egress firewall (or a microVM/gVisor sandbox) at
# the production scale-up path. Determined code can still open a raw fd; the OS layer is what
# makes "no network" enforceable.
_RUNNER_PREAMBLE: Final[str] = (
    "import sys as _sys\n"
    "_sys.path[:] = [p for p in _sys.path if p not in ('', '.')]\n"
    "import socket as _socket\n"
    "def _no_network(*_a, **_k):\n"
    "    raise OSError('network access is disabled in the execute_python sandbox')\n"
    "_socket.socket = _no_network\n"
    "_socket.create_connection = _no_network\n"
    "_socket.create_server = _no_network\n"
)


class ExecutePythonArgs(BaseModel):
    code: str = Field(
        description=(
            "A self-contained Python 3 snippet. It runs with no network, no input, a CPU "
            "and wall-clock timeout, and memory/file-size limits, in an empty temporary "
            "directory. Print results to stdout — the return value of the snippet is ignored. "
            "Only the standard library is available."
        )
    )


class ExecutePythonResult(BaseModel):
    ok: bool = Field(description="Whether the snippet exited 0 within all limits.")
    stdout: str = Field(description="Captured standard output, truncated to the output cap.")
    stderr: str = Field(description="Captured standard error (tracebacks land here), truncated.")
    exit_code: int | None = Field(
        default=None, description="Process exit code, or null if it was killed by a signal."
    )
    timed_out: bool = Field(description="Whether the wall-clock timeout killed the process group.")
    truncated: bool = Field(description="Whether stdout or stderr was truncated to the cap.")


def _current_uid_process_count() -> int:
    try:
        output: str = subprocess.run(
            ["ps", "-u", str(os.getuid()), "-o", "pid="],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in output.splitlines() if line.strip())


def _apply_child_limits(
    *, cpu_seconds: int, address_space_bytes: int, file_size_bytes: int, max_processes: int
) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_bytes, file_size_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if hasattr(resource, "RLIMIT_NPROC"):
        # Bound fork bombs. RLIMIT_NPROC counts EVERY process this real UID already owns on
        # the host, so the caller passes an ABSOLUTE ceiling = current live count + headroom;
        # a value at or below the live count would block the child's own exec. Best-effort:
        # if the hard limit is lower we clamp to it, and any rejection leaves the wall-clock
        # timeout and CPU rlimit as the binding limits.
        _, nproc_hard = resource.getrlimit(resource.RLIMIT_NPROC)
        ceiling: int = max_processes if nproc_hard < 0 else min(max_processes, nproc_hard)
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(resource.RLIMIT_NPROC, (ceiling, ceiling))
    if sys.platform == "linux":
        # RLIMIT_AS only constrains the address space reliably on Linux. macOS/Darwin
        # accounts virtual memory through Mach and rejects the call with
        # "ValueError: current limit exceeds maximum limit", so skip it off-Linux —
        # the dev box still gets CPU + wall-clock + fork bounds, just not a hard memory cap.
        resource.setrlimit(resource.RLIMIT_AS, (address_space_bytes, address_space_bytes))


def _preexec(
    *, cpu_seconds: int, address_space_bytes: int, file_size_bytes: int, max_processes: int
) -> None:
    # No os.setsid() here: create_subprocess_exec(start_new_session=True) already makes the
    # child a session/process-group leader, so the group is killable via os.killpg. Calling
    # setsid() a second time fails with EPERM (a leader can't create a new session) and the
    # whole spawn aborts as an opaque "Exception occurred in preexec_fn".
    _apply_child_limits(
        cpu_seconds=cpu_seconds,
        address_space_bytes=address_space_bytes,
        file_size_bytes=file_size_bytes,
        max_processes=max_processes,
    )


def _minimal_env(workdir: str) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": workdir,
        "TMPDIR": workdir,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    }


async def _terminate_group(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process_group_id: int = os.getpgid(process.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=_KILL_GRACE_S)
    except TimeoutError:
        log.warning("execute_python_reap_slow", pid=process.pid)


def register_execute_python(registry: ToolRegistry) -> None:
    @registry.tool(permission=Permission.ASK)
    async def execute_python(args: ExecutePythonArgs) -> ExecutePythonResult:
        """Run a short, self-contained Python 3 snippet and return its stdout/stderr.

        Use this for calculation and data wrangling the model should not do in its head:
        arithmetic, date math, parsing a value out of fetched text, small table transforms.
        The snippet runs in a locked-down subprocess — no network, no filesystem outside a
        scratch directory, hard CPU/memory/time limits — so write defensive code and print
        what you want to keep; anything not printed is lost. The standard library only.
        """
        settings = get_settings()
        cpu_seconds: int = settings.exec_cpu_seconds
        address_space_bytes: int = settings.exec_memory_mb * 1024 * 1024
        file_size_bytes: int = settings.exec_file_size_mb * 1024 * 1024
        output_cap: int = settings.exec_max_output_chars
        # RLIMIT_NPROC is per-UID over the whole host, so the ceiling is the parent's live
        # process count plus a small headroom; computing it here (before fork) keeps preexec
        # trivial and avoids a value that would block the child's own exec.
        nproc_ceiling: int = (
            await asyncio.to_thread(_current_uid_process_count) + settings.exec_max_processes
        )

        workdir: str = tempfile.mkdtemp(prefix="argus-exec-")
        try:
            process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                _RUNNER_PREAMBLE + args.code,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                env=_minimal_env(workdir),
                start_new_session=True,
                preexec_fn=lambda: _preexec(
                    cpu_seconds=cpu_seconds,
                    address_space_bytes=address_space_bytes,
                    file_size_bytes=file_size_bytes,
                    max_processes=nproc_ceiling,
                ),
            )

            timed_out: bool = False
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=settings.exec_timeout_s
                )
            except TimeoutError:
                timed_out = True
                await _terminate_group(process)
                stdout_bytes, stderr_bytes = b"", b""
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        stdout_full: str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_full: str = stderr_bytes.decode("utf-8", errors="replace")
        if timed_out and not stderr_full:
            stderr_full = f"[killed: exceeded {settings.exec_timeout_s:g}s wall-clock limit]"
        truncated: bool = len(stdout_full) > output_cap or len(stderr_full) > output_cap

        exit_code: int | None = process.returncode
        ok: bool = exit_code == 0 and not timed_out
        log.info(
            "execute_python",
            ok=ok,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_chars=len(stdout_full),
            stderr_chars=len(stderr_full),
        )
        return ExecutePythonResult(
            ok=ok,
            stdout=stdout_full[:output_cap],
            stderr=stderr_full[:output_cap],
            exit_code=exit_code,
            timed_out=timed_out,
            truncated=truncated,
        )
