"""Structured logging via structlog: console for dev, JSON for prod."""

from __future__ import annotations

import logging
import sys
from typing import Any

import orjson
import structlog

_is_configured: bool = False


def _orjson_serializer(obj: Any, default: Any = None, **_: Any) -> str:
    return orjson.dumps(obj, default=default).decode()


def configure_logging(*, level: str = "INFO", json: bool = False) -> None:
    global _is_configured
    if _is_configured:
        return

    level_number: int = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    renderer: Any = (
        structlog.processors.JSONRenderer(serializer=_orjson_serializer)
        if json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_number),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _is_configured = True


def get_logger(name: str | None = None) -> Any:
    if not _is_configured:
        configure_logging()
    return structlog.get_logger(name)
