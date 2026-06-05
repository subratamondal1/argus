from __future__ import annotations

import uuid

import pytest

from argus.auth import (
    AuthError,
    decode_token,
    issue_token,
    login,
    signup,
    tenant_from_authorization,
)


def test_token_roundtrip() -> None:
    token = issue_token("uid-1", "a@b.com", "tenant-1")
    claims = decode_token(token)
    assert claims is not None
    assert claims["sub"] == "uid-1"
    assert claims["email"] == "a@b.com"
    assert claims["tenant"] == "tenant-1"


def test_decode_rejects_garbage() -> None:
    assert decode_token("not.a.jwt") is None


def test_tenant_from_authorization() -> None:
    token = issue_token("uid-1", "a@b.com", "tenant-xyz")
    assert tenant_from_authorization(f"Bearer {token}") == "tenant-xyz"
    assert tenant_from_authorization(None) is None
    assert tenant_from_authorization("Basic abc") is None
    assert tenant_from_authorization("Bearer not-a-token") is None


def test_resolve_tenant_is_jwt_only_and_fails_closed() -> None:
    from argus.web.errors import ApiError
    from argus.web.server import _resolve_tenant

    assert _resolve_tenant(None) == "public"  # anonymous -> shared public corpus only
    token = issue_token("u1", "a@b.com", "tenant-secret")
    assert _resolve_tenant(f"Bearer {token}") == "tenant-secret"
    with pytest.raises(ApiError):  # present-but-invalid token fails CLOSED (no header fallback)
        _resolve_tenant("Bearer tampered.garbage.token")
    with pytest.raises(ApiError):
        _resolve_tenant("Basic abc")


def test_default_jwt_secret_blocked_in_production() -> None:
    from pydantic import ValidationError

    from argus.config import _DEFAULT_JWT_SECRET, Settings

    real: str = "x" * 40
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret=_DEFAULT_JWT_SECRET, csrf_secret=real)
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="too-short", csrf_secret=real)
    with pytest.raises(ValidationError):  # the CSRF secret is guarded the same way
        Settings(environment="production", jwt_secret=real, csrf_secret=_DEFAULT_JWT_SECRET)
    Settings(environment="production", jwt_secret=real, csrf_secret="y" * 40)  # both real: ok
    Settings(environment="development", jwt_secret=_DEFAULT_JWT_SECRET)  # dev allows the default


@pytest.mark.integration
async def test_signup_login_flow() -> None:
    import asyncpg

    from argus.config import get_settings
    from argus.db import close_pool, get_pool

    settings = get_settings()
    try:
        probe = await asyncpg.connect(settings.database_url)
        await probe.close()
    except Exception:
        pytest.skip(f"no Postgres at {settings.database_url}")

    email = f"itest-{uuid.uuid4().hex[:8]}@example.com"
    pool = await get_pool()
    try:
        created = await signup(email, "password123")
        assert created.email == email
        assert created.tenant == created.user_id  # one isolated tenant per user
        assert created.token

        signed_in = await login(email, "password123")
        assert signed_in.user_id == created.user_id

        with pytest.raises(AuthError):
            await login(email, "wrong-password")
        with pytest.raises(AuthError):
            await signup(email, "password123")  # duplicate email
        with pytest.raises(AuthError):
            await signup("x@y.com", "short")  # password too short
    finally:
        async with pool.acquire() as connection:
            await connection.execute("DELETE FROM users WHERE email = $1", email)
        await close_pool()
