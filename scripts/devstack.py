"""Idempotent dev-stack launcher with dynamic free-port selection for SearXNG."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from time import sleep

PROJECT_DIR: Path = Path(__file__).resolve().parent.parent
ENV_FILE: Path = PROJECT_DIR / ".env"
CONTAINER: str = "argus-searxng"
INTERNAL_PORT: int = 8080
BASE_PORT: int = 8080
PORT_SPAN: int = 20
PORT_ENV_KEY: str = "ARGUS_SEARXNG_PORT"


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], cwd=PROJECT_DIR, capture_output=True, text=True)


def _running_host_port() -> int | None:
    result = _docker("port", CONTAINER, f"{INTERNAL_PORT}/tcp")
    first_line: str = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if result.returncode != 0 or not first_line:
        return None
    return int(first_line.rsplit(":", 1)[1])


def _is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def _first_free_port() -> int:
    for port in range(BASE_PORT, BASE_PORT + PORT_SPAN):
        if _is_free(port):
            return port
    raise RuntimeError(f"no free port found in range {BASE_PORT}-{BASE_PORT + PORT_SPAN - 1}")


def _write_port(port: int) -> None:
    line: str = f"{PORT_ENV_KEY}={port}"
    existing: list[str] = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    written: list[str] = []
    replaced: bool = False
    for entry in existing:
        if entry.startswith(f"{PORT_ENV_KEY}="):
            written.append(line)
            replaced = True
        else:
            written.append(entry)
    if not replaced:
        written.append(line)
    ENV_FILE.write_text("\n".join(written) + "\n")


def _wait_ready(port: int, attempts: int = 30, delay_s: float = 1.0) -> bool:
    url: str = f"http://localhost:{port}/"
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            sleep(delay_s)
    return False


def _compose_up(port: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=PROJECT_DIR,
        env={**os.environ, PORT_ENV_KEY: str(port)},
        capture_output=True,
        text=True,
    )


def up() -> int:
    running: int | None = _running_host_port()
    if running is not None:
        _write_port(running)
        print(f"argus-searxng already live at http://localhost:{running}")
        return 0

    port: int = _first_free_port()
    _write_port(port)
    result = _compose_up(port)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    if not _wait_ready(port):
        print(f"argus-searxng started on {port} but did not become ready in time", file=sys.stderr)
        return 1
    print(f"argus-searxng started at http://localhost:{port}")
    return 0


def down() -> int:
    result = _docker("compose", "down")
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    print("argus-searxng stopped")
    return 0


def status() -> int:
    running: int | None = _running_host_port()
    if running is None:
        print("argus-searxng is not running")
        return 0
    print(f"argus-searxng live at http://localhost:{running}")
    return 0


def main() -> int:
    command: str = sys.argv[1] if len(sys.argv) > 1 else "up"
    actions: dict[str, Callable[[], int]] = {"up": up, "down": down, "status": status}
    action: Callable[[], int] | None = actions.get(command)
    if action is None:
        print("usage: devstack.py [up|down|status]", file=sys.stderr)
        return 2
    try:
        return action()
    except FileNotFoundError:
        print("docker not found on PATH; is Docker installed and running?", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
