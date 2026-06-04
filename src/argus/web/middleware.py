"""A pure-ASGI request-id middleware (no BaseHTTPMiddleware, per the stack rules).

Every request gets a correlation id — generated, or echoed from an inbound
`X-Request-Id` — bound into structlog's contextvars so it tags every log line for
the request's lifetime, and returned on the response so a client can quote it.
The agent run binds an additional `run_id` (see web.server) under the same id, so
the planner and every fanned-out searcher coroutine thread back to one request.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

_HEADER: bytes = b"x-request-id"


class RequestIdMiddleware:
    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers: dict[bytes, bytes] = dict(scope.get("headers", []))
        inbound: bytes | None = headers.get(_HEADER)
        request_id: str = inbound.decode() if inbound else uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_header(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (_HEADER, request_id.encode()),
                ]
            await send(message)

        try:
            await self._app(scope, receive, send_with_header)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
