"""Idempotent dev-stack launcher + status, with structured logging.

Run via `uv run` (the Makefile targets do) so this shares the app's structlog
config and emits the same structured events as the rest of Argus. `up` starts the
Docker backing services — SearXNG (always) and Postgres/pgvector (the `data`
compose profile, which gates the DB so it isn't started by a bare `compose up`).
`status` probes every service the app talks to, including the native Ollama server
and the running app/frontend, and reports each as up/down. `down` stops the Docker
services.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import sleep

from argus.logging import configure_logging, get_logger

log = get_logger("devstack")

PROJECT_DIR: Path = Path(__file__).resolve().parent.parent
ENV_FILE: Path = PROJECT_DIR / ".env"
CONTAINER: str = "argus-searxng"
INTERNAL_PORT: int = 8080
BASE_PORT: int = 8080
PORT_SPAN: int = 20
PORT_ENV_KEY: str = "ARGUS_SEARXNG_PORT"
COMPOSE_PROFILE: str = "data"  # gates the Postgres service in docker-compose.yml


@dataclass(frozen=True)
class Service:
    name: str
    port: int
    managed: bool  # True = started by `up` (Docker); False = probed-only (native/app/optional)
    note: str = ""
    # An HTTP path to GET for liveness; truer than a raw TCP probe (a held port or a
    # hung server reads as "up" on TCP but fails here). None -> plain TCP (pg/redis).
    health_path: str | None = None


def _services(searxng_port: int) -> list[Service]:
    return [
        Service("searxng", searxng_port, managed=True, health_path="/"),
        Service("postgres", 5432, managed=True),
        Service("ollama", 11434, managed=False, note="native app", health_path="/api/version"),
        Service("redis", 6379, managed=False, note="optional — only with ARGUS_USE_QUEUE=true"),
        Service(
            "argus-api",
            8000,
            managed=False,
            note="`make serve`/`make web`",
            health_path="/api/health",
        ),
        Service("frontend", 3000, managed=False, note="`make web`", health_path="/"),
    ]


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], cwd=PROJECT_DIR, capture_output=True, text=True)


def _running_host_port() -> int | None:
    result = _docker("port", CONTAINER, f"{INTERNAL_PORT}/tcp")
    first_line: str = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if result.returncode != 0 or not first_line:
        return None
    return int(first_line.rsplit(":", 1)[1])


def _env_port() -> int:
    if ENV_FILE.exists():
        for entry in ENV_FILE.read_text().splitlines():
            if entry.startswith(f"{PORT_ENV_KEY}="):
                return int(entry.split("=", 1)[1])
    return BASE_PORT


def _tcp_alive(port: int, timeout_s: float = 1.0) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _http_ok(port: int, path: str, timeout_s: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=timeout_s):
            return True
    except urllib.error.HTTPError:
        return True  # the server answered (even a 4xx) -> it's up and serving
    except (urllib.error.URLError, OSError):
        return False


def _alive(service: Service) -> bool:
    if service.health_path is not None:
        return _http_ok(service.port, service.health_path)
    return _tcp_alive(service.port)


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


def _wait_http(port: int, attempts: int = 30, delay_s: float = 1.0) -> bool:
    url: str = f"http://localhost:{port}/"
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            sleep(delay_s)
    return False


def _wait_tcp(port: int, attempts: int = 30, delay_s: float = 1.0) -> bool:
    for _ in range(attempts):
        if _tcp_alive(port):
            return True
        sleep(delay_s)
    return False


def _compose_up(port: int) -> subprocess.CompletedProcess[str]:
    # The `data` profile pulls in Postgres alongside the always-on SearXNG; without
    # it a bare `compose up` starts SearXNG only and the DB-backed paths (RAG, eval,
    # history) fail at connect time.
    return subprocess.run(
        ["docker", "compose", "--profile", COMPOSE_PROFILE, "up", "-d"],
        cwd=PROJECT_DIR,
        env={**os.environ, PORT_ENV_KEY: str(port)},
        capture_output=True,
        text=True,
    )


def _report(searxng_port: int) -> None:
    for service in _services(searxng_port):
        alive: bool = _alive(service)
        status_word: str = "up" if alive else "down"
        emit = log.info if (alive or not service.managed) else log.warning
        fields: dict[str, str] = {"url": f"http://localhost:{service.port}"}
        if service.note:
            fields["note"] = service.note
        emit("service", name=service.name, status=status_word, **fields)


def up() -> int:
    port: int = _running_host_port() or _first_free_port()
    _write_port(port)
    log.info("devstack_up", searxng_port=port, profile=COMPOSE_PROFILE)
    result = _compose_up(port)
    if result.returncode != 0:
        log.error("compose_up_failed", error=result.stderr.strip())
        return result.returncode
    if _wait_http(port):
        log.info("searxng_ready", port=port)
    else:
        log.warning("searxng_not_ready", port=port)
    if _wait_tcp(5432):
        log.info("postgres_ready", port=5432)
    else:
        log.warning("postgres_not_ready", port=5432)
    _report(port)
    return 0


def down() -> int:
    result = _docker("compose", "--profile", COMPOSE_PROFILE, "down")
    if result.returncode != 0:
        log.error("compose_down_failed", error=result.stderr.strip())
        return result.returncode
    log.info("devstack_down")
    return 0


def status() -> int:
    _report(_running_host_port() or _env_port())
    return 0


def main() -> int:
    configure_logging(level="INFO", json=False)
    command: str = sys.argv[1] if len(sys.argv) > 1 else "up"
    actions: dict[str, Callable[[], int]] = {"up": up, "down": down, "status": status}
    action: Callable[[], int] | None = actions.get(command)
    if action is None:
        log.error("usage", expected="devstack.py [up|down|status]", got=command)
        return 2
    try:
        return action()
    except FileNotFoundError:
        log.error("docker_not_found", hint="is Docker installed and running?")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
