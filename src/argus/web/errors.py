"""A stable JSON error envelope for the HTTP API.

Every error — a raised ApiError, a FastAPI/Starlette HTTPException, a request
validation failure, or an unexpected exception — renders the SAME shape, so a
client can branch on a stable machine-readable `code` and quote the `request_id`:

    {"error": {"code": "unprocessable_source", "message": "...", "request_id": "..."}}

The 4xx handlers run inside the CORS layer (Starlette's ExceptionMiddleware), so
their responses keep CORS headers; the request id is read from the contextvar the
RequestIdMiddleware binds.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import orjson
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from argus.logging import get_logger

log = get_logger(__name__)


class ApiError(Exception):
    """A client-facing error carrying a stable code and an HTTP status."""

    def __init__(self, *, code: str, status: int, message: str) -> None:
        super().__init__(message)
        self.code: str = code
        self.status: int = status
        self.message: str = message


def _request_id() -> str | None:
    value: Any = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None


def _envelope(*, code: str, status: int, message: str) -> Response:
    payload: dict[str, Any] = {
        "error": {"code": code, "message": message, "request_id": _request_id()}
    }
    return Response(
        content=orjson.dumps(payload), status_code=status, media_type="application/json"
    )


# Stable code for a bare HTTPException raised without one of our own codes.
_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _on_api_error(_request: Request, error: ApiError) -> Response:
        return _envelope(code=error.code, status=error.status, message=error.message)

    @app.exception_handler(StarletteHTTPException)
    async def _on_http_error(_request: Request, error: StarletteHTTPException) -> Response:
        code: str = _STATUS_CODES.get(error.status_code, "http_error")
        message: str = error.detail if isinstance(error.detail, str) else code.replace("_", " ")
        return _envelope(code=code, status=error.status_code, message=message)

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_request: Request, error: RequestValidationError) -> Response:
        errors: Sequence[Any] = error.errors()
        message: str = "invalid request"
        if errors:
            location: str = ".".join(
                str(part) for part in errors[0].get("loc", ()) if part != "body"
            )
            detail: str = str(errors[0].get("msg", "invalid"))
            message = f"{location}: {detail}" if location else detail
        return _envelope(code="validation_error", status=422, message=message)

    @app.exception_handler(Exception)
    async def _on_unexpected(request: Request, error: Exception) -> Response:
        log.error("unhandled_error", error=str(error), path=request.url.path)
        return _envelope(code="internal_error", status=500, message="An unexpected error occurred.")
