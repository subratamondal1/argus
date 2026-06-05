from __future__ import annotations

import uuid

import httpx
import pytest

from argus.auth import issue_token
from argus.config import get_settings
from argus.csrf import issue_csrf_token, verify_csrf_token
from argus.web import server as web

ORIGIN = "http://localhost:3000"


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=web.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _session(tenant: str = "tenant-1") -> dict[str, str]:
    return {get_settings().cookie_name: issue_token("u1", "a@b.com", tenant)}


def _csrf() -> str:
    return issue_csrf_token(get_settings().csrf_secret)


# --- csrf.py unit tests ---------------------------------------------------------


def test_csrf_roundtrip_and_tamper() -> None:
    secret = "unit-test-secret"
    token = issue_csrf_token(secret)
    assert verify_csrf_token(token, token, secret) is True  # double-submit match + signed
    assert verify_csrf_token(token, "other", secret) is False  # header != cookie
    assert verify_csrf_token(token, token, "different-secret") is False  # bad signature
    assert verify_csrf_token("abc.deadbeef", "abc.deadbeef", secret) is False  # forged, unsigned
    assert verify_csrf_token(None, token, secret) is False
    assert verify_csrf_token(token, None, secret) is False


# --- cookie auth happy paths ----------------------------------------------------


async def test_login_sets_httponly_session_and_readable_csrf_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.auth import AuthResult

    async def fake_login(email: str, password: str) -> AuthResult:
        return AuthResult(issue_token("u1", email, "tenant-1"), "u1", email, "tenant-1")

    monkeypatch.setattr(web, "login", fake_login)

    async with _client() as client:
        response = await client.post(
            "/api/auth/login", json={"email": "a@b.com", "password": "password123"}
        )
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith(f"{get_settings().cookie_name}="))
    csrf = next(c for c in cookies if c.startswith(f"{get_settings().csrf_cookie_name}="))
    assert "httponly" in session.lower()  # JWT cookie is not JS-readable
    assert "httponly" not in csrf.lower()  # CSRF cookie must be readable by the SPA


async def test_cookie_auth_reads_the_token_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.conversations import ConversationSummary

    seen: dict[str, str] = {}

    async def fake_list(tenant: str) -> list[ConversationSummary]:
        seen["tenant"] = tenant
        return []

    monkeypatch.setattr(web, "list_conversations", fake_list)

    async with _client() as client:
        response = await client.get("/api/conversations", cookies=_session("acct-cookie"))
    assert response.status_code == 200  # GET needs no CSRF
    assert seen["tenant"] == "acct-cookie"


# --- CSRF enforcement on the cookie path ----------------------------------------


async def _put(
    client: httpx.AsyncClient,
    *,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.put(
        f"/api/conversations/{uuid.uuid4()}",
        json={"title": "x", "turns": []},
        cookies=cookies,
        headers=headers,
    )


async def test_cookie_mutation_requires_csrf(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    async def fake_upsert(*args: object, **kwargs: object) -> datetime:
        return datetime(2026, 6, 4, tzinfo=UTC)

    monkeypatch.setattr(web, "upsert_conversation", fake_upsert)
    token = _csrf()

    async with _client() as client:
        # No CSRF token -> 403.
        missing = await _put(client, cookies=_session(), headers={"origin": ORIGIN})
        # Mismatched token -> 403.
        mismatched = await _put(
            client,
            cookies={**_session(), get_settings().csrf_cookie_name: token},
            headers={"origin": ORIGIN, "X-CSRF-Token": "not-the-token"},
        )
        # Forged (valid double-submit, bad signature) -> 403.
        forged = await _put(
            client,
            cookies={**_session(), get_settings().csrf_cookie_name: "abc.deadbeef"},
            headers={"origin": ORIGIN, "X-CSRF-Token": "abc.deadbeef"},
        )
        # Full, valid CSRF -> succeeds.
        ok = await _put(
            client,
            cookies={**_session(), get_settings().csrf_cookie_name: token},
            headers={"origin": ORIGIN, "X-CSRF-Token": token},
        )
    assert missing.status_code == 403 and missing.json()["error"]["code"] == "csrf_token"
    assert mismatched.status_code == 403
    assert forged.status_code == 403
    assert ok.status_code == 200


async def test_cookie_mutation_origin_gate() -> None:
    token = _csrf()
    csrf_cookies = {**_session(), get_settings().csrf_cookie_name: token}
    async with _client() as client:
        evil = await _put(
            client,
            cookies=csrf_cookies,
            headers={"origin": "https://evil.com", "X-CSRF-Token": token},
        )
        absent = await _put(client, cookies=csrf_cookies, headers={"X-CSRF-Token": token})
    assert evil.status_code == 403 and evil.json()["error"]["code"] == "csrf_origin"
    assert absent.status_code == 403  # no Origin and no Referer


async def test_referer_prefix_lookalike_is_blocked() -> None:
    # A Referer-only request (no Origin) from a lookalike host that merely *prefixes*
    # an allowed origin must not slip past the boundary check.
    token = _csrf()
    async with _client() as client:
        response = await _put(
            client,
            cookies={**_session(), get_settings().csrf_cookie_name: token},
            headers={"referer": f"{ORIGIN}.evil.com/page", "X-CSRF-Token": token},
        )
    assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_origin"


async def test_cookie_mutation_content_type_gate() -> None:
    token = _csrf()
    async with _client() as client:
        response = await client.post(
            "/api/ask",
            content=b"question=hi",
            cookies={**_session(), get_settings().csrf_cookie_name: token},
            headers={
                "origin": ORIGIN,
                "X-CSRF-Token": token,
                "content-type": "text/plain",
            },
        )
    assert response.status_code == 415 and response.json()["error"]["code"] == "csrf_content_type"


# --- dual-path precedence -------------------------------------------------------


async def test_header_auth_is_csrf_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    captured: dict[str, object] = {}

    async def fake_upsert(
        tenant: str, conversation_id: str, title: str, turns: list[dict[str, object]]
    ) -> datetime:
        captured["tenant"] = tenant
        return datetime(2026, 6, 4, tzinfo=UTC)

    monkeypatch.setattr(web, "upsert_conversation", fake_upsert)
    async with _client() as client:
        # Bearer header, NO cookie, NO CSRF token -> still works (header is CSRF-immune).
        response = await _put(
            client,
            headers={"Authorization": f"Bearer {issue_token('u1', 'a@b.com', 'hdr-tenant')}"},
        )
    assert response.status_code == 200
    assert captured["tenant"] == "hdr-tenant"


async def test_header_wins_and_fails_closed() -> None:
    token = _csrf()
    async with _client() as client:
        # Valid Bearer + a cookie, no CSRF -> header path wins -> exempt -> succeeds is
        # covered above; here: an INVALID Bearer must fail closed, never fall back to the cookie.
        response = await _put(
            client,
            cookies={**_session("cookie-tenant"), get_settings().csrf_cookie_name: token},
            headers={
                "Authorization": "Bearer tampered.garbage",
                "origin": ORIGIN,
                "X-CSRF-Token": token,
            },
        )
    assert response.status_code == 401  # invalid header is rejected, cookie is NOT consulted


async def test_logout_clears_cookies() -> None:
    async with _client() as client:
        response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    cleared = " ".join(response.headers.get_list("set-cookie"))
    assert get_settings().cookie_name in cleared
    assert get_settings().csrf_cookie_name in cleared
