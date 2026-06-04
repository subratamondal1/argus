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
