"""Signed double-submit CSRF tokens.

When auth moves from an Authorization header to an httpOnly cookie, the browser
auto-sends the session on every request — including ones a malicious site forges
(CSRF). The defense here: mint a random token, HMAC-sign it, and put it in a
JS-readable cookie; the SPA echoes it in a request header. A request passes only
when the header equals the cookie (double-submit) AND the signature verifies (so a
sibling-subdomain attacker can't inject a cookie we'd accept). This is checked only
for cookie-authenticated mutating requests — Authorization-header auth is
structurally CSRF-immune (the browser never auto-attaches it), so it's exempt.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def issue_csrf_token(secret: str) -> str:
    raw: str = secrets.token_urlsafe(32)
    mac: str = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{mac}"


def verify_csrf_token(cookie_value: str | None, header_value: str | None, secret: str) -> bool:
    if not cookie_value or not header_value:
        return False
    if not hmac.compare_digest(cookie_value, header_value):  # double-submit: header == cookie
        return False
    raw, _, mac = cookie_value.partition(".")
    if not mac:
        return False
    expected: str = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, expected)  # signed: we are the only minter
