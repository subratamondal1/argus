"""Email/password auth: argon2 hashing + HS256 JWTs, each user bound to a tenant.

Signup mints a user with a fresh tenant id, so a user's ingested corpus and
research are isolated by the tenant filter already enforced in the RAG layer. The
JWT carries (sub, email, tenant); the API reads the tenant from a verified token
and scopes retrieval to it. Password hashes are argon2id (the OWASP default);
verification is constant-time, and login returns the same error for an unknown
email and a wrong password so it can't be used to enumerate accounts.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import argon2
import asyncpg
import jwt

from argus.config import get_settings
from argus.db import get_pool
from argus.logging import get_logger

log = get_logger(__name__)

_HASHER: argon2.PasswordHasher = argon2.PasswordHasher()
_ALGORITHM: str = "HS256"
_MIN_PASSWORD: int = 8


class AuthError(Exception):
    """A signup/login failure surfaced to the client (bad credentials, dup email)."""


@dataclass(frozen=True)
class AuthResult:
    token: str
    user_id: str
    email: str
    tenant: str


def issue_token(user_id: str, email: str, tenant: str) -> str:
    settings = get_settings()
    now: int = int(time.time())
    payload: dict[str, object] = {
        "sub": user_id,
        "email": email,
        "tenant": tenant,
        "iat": now,
        "exp": now + settings.jwt_expiry_s,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, str] | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None


def tenant_from_authorization(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    claims: dict[str, str] | None = decode_token(authorization.split(" ", 1)[1].strip())
    tenant: object = claims.get("tenant") if claims else None
    return tenant if isinstance(tenant, str) else None


async def signup(email: str, password: str) -> AuthResult:
    normalized: str = email.strip().lower()
    if "@" not in normalized or len(password) < _MIN_PASSWORD:
        raise AuthError(f"a valid email and a password of at least {_MIN_PASSWORD} characters")
    user_uuid: uuid.UUID = uuid.uuid4()
    user_id: str = str(user_uuid)
    tenant: str = user_id  # one isolated tenant per user
    pool = await get_pool()
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO users (id, email, password_hash, tenant) VALUES ($1, $2, $3, $4)",
                user_uuid,
                normalized,
                _HASHER.hash(password),
                tenant,
            )
    except asyncpg.UniqueViolationError as error:
        raise AuthError("that email is already registered") from error
    log.info("signup", email=normalized)
    return AuthResult(issue_token(user_id, normalized, tenant), user_id, normalized, tenant)


async def login(email: str, password: str) -> AuthResult:
    normalized: str = email.strip().lower()
    pool = await get_pool()
    async with pool.acquire() as connection:
        row: asyncpg.Record | None = await connection.fetchrow(
            "SELECT id::text AS id, password_hash, tenant FROM users WHERE email = $1", normalized
        )
    if row is None or not _verify(password, row["password_hash"]):
        raise AuthError("invalid email or password")
    log.info("login", email=normalized)
    return AuthResult(
        issue_token(row["id"], normalized, row["tenant"]), row["id"], normalized, row["tenant"]
    )


def _verify(password: str, password_hash: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except argon2.exceptions.VerificationError:
        return False
