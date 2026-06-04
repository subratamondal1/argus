"""A pure-ASGI per-client rate limiter backed by a Redis sliding window.

Redis-backed (not in-memory) so the limit holds across API replicas behind a load
balancer — the same reason the searcher queue is on Redis. The window is a sorted
set per client; an atomic Lua script trims expired entries, counts, and admits or
rejects in one round-trip (no check-then-act race). It FAILS OPEN: if Redis is
unreachable the request is allowed, so the limiter can never take the API down.
Health/readiness probes are exempt so autoscalers/k8s are never throttled.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable
from typing import Any, cast

import orjson
import redis.asyncio as aioredis
import structlog

from argus.config import Settings
from argus.logging import get_logger

log = get_logger(__name__)

_EXEMPT_PATHS: frozenset[str] = frozenset({"/api/health", "/api/ready"})

# Atomic sliding-window admission. KEYS[1] = client bucket; ARGV = now_ms, window_ms,
# limit, member. Returns remaining quota (>=0) when admitted, or -1 when over limit.
_SCRIPT: str = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
  redis.call('ZADD', key, now, ARGV[4])
  redis.call('PEXPIRE', key, window)
  return limit - count - 1
end
return -1
"""


def _client_id(scope: dict[str, Any]) -> str:
    headers: dict[bytes, bytes] = dict(scope.get("headers", []))
    forwarded: bytes | None = headers.get(b"x-forwarded-for")
    if forwarded:
        return forwarded.decode().split(",")[0].strip()
    client: Any = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    def __init__(self, app: Any, settings: Settings) -> None:
        self._app = app
        self._settings = settings
        self._redis: aioredis.Redis | None = None
        self._window_ms: int = int(settings.rate_limit_window_s * 1000)

    def _pool(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._settings.redis_url)
        return self._redis

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            not self._settings.rate_limit_enabled
            or scope["type"] != "http"
            or scope.get("path") in _EXEMPT_PATHS
        ):
            await self._app(scope, receive, send)
            return

        bucket: str = f"argus:ratelimit:{_client_id(scope)}"
        now_ms: int = int(time.time() * 1000)
        try:
            # Args are passed as strings (the Lua script tonumber()s them); cast the
            # eval result because redis-py types eval for both sync and async clients.
            outcome: Any = await cast(
                Awaitable[Any],
                self._pool().eval(
                    _SCRIPT,
                    1,
                    bucket,
                    str(now_ms),
                    str(self._window_ms),
                    str(self._settings.rate_limit_requests),
                    uuid.uuid4().hex,
                ),
            )
            remaining: int = int(outcome)
        except Exception as error:
            # Fail open — a rate limiter must never be the reason the API is down.
            log.warning("rate_limit_unavailable", error=str(error))
            await self._app(scope, receive, send)
            return

        if remaining < 0:
            await self._reject(send)
            return
        await self._app(scope, receive, send)

    async def _reject(self, send: Any) -> None:
        request_id: Any = structlog.contextvars.get_contextvars().get("request_id")
        body: bytes = orjson.dumps(
            {
                "error": {
                    "code": "rate_limited",
                    "message": "Too many requests — slow down.",
                    "request_id": request_id if isinstance(request_id, str) else None,
                }
            }
        )
        retry_after: str = str(max(1, int(self._settings.rate_limit_window_s)))
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", retry_after.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
