from __future__ import annotations

import uuid
from typing import Any, cast

import httpx
import pytest

from argus.config import Settings
from argus.web.ratelimit import RateLimitMiddleware


async def _ok_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


@pytest.mark.integration
async def test_rate_limiter_429s_after_the_limit() -> None:
    import redis.asyncio as aioredis

    settings = Settings()
    probe = aioredis.from_url(settings.redis_url)
    try:
        await probe.ping()
    except Exception:
        pytest.skip(f"no Redis reachable at {settings.redis_url}")
    finally:
        await probe.aclose()

    limiter = RateLimitMiddleware(
        _ok_app,
        settings=Settings(rate_limit_enabled=True, rate_limit_requests=3, rate_limit_window_s=60.0),
    )
    client_id = uuid.uuid4().hex  # unique bucket per run — no cross-run interference
    transport = httpx.ASGITransport(app=cast(Any, limiter))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        responses = [
            await client.get("/api/ask", headers={"X-Forwarded-For": client_id}) for _ in range(5)
        ]

    statuses = [response.status_code for response in responses]
    assert statuses == [200, 200, 200, 429, 429]  # first 3 admitted, rest rejected
    rejected = responses[3]
    assert rejected.json()["error"]["code"] == "rate_limited"
    assert int(rejected.headers["retry-after"]) >= 1


async def test_rate_limiter_disabled_passes_through() -> None:
    # Default settings have it off — no Redis touched, every request admitted.
    limiter = RateLimitMiddleware(_ok_app, settings=Settings())
    transport = httpx.ASGITransport(app=cast(Any, limiter))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        for _ in range(10):
            assert (await client.get("/api/ask")).status_code == 200
