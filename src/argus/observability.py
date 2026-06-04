"""Optional OpenTelemetry tracing: FastAPI + asyncpg + httpx -> OTLP -> Jaeger.

Lazy-imports the otel SDK (the `otel` extra) so the core stays dependency-light,
and is a no-op when ARGUS_OTEL_ENABLED is false. Auto-instrumentation traces each
request end to end: the HTTP span, the pgvector queries (asyncpg), and every
outbound httpx call (LiteLLM providers, SearXNG, web_fetch) as child spans.
"""

from __future__ import annotations

from fastapi import FastAPI

from argus.config import Settings
from argus.logging import get_logger

log = get_logger(__name__)


def setup_tracing(app: FastAPI, settings: Settings) -> None:
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("otel_extra_missing", hint="uv sync --extra otel")
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    exporter = OTLPSpanExporter(endpoint=f"{settings.otel_endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    AsyncPGInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    log.info(
        "otel_tracing_enabled",
        endpoint=settings.otel_endpoint,
        service=settings.otel_service_name,
    )


def setup_langfuse(settings: Settings) -> None:
    if not settings.langfuse_enabled:
        return
    import litellm

    # LiteLLM's langfuse_otel callback ships a trace per LLM call (prompt, model,
    # tokens, cost, latency) to Langfuse; the public/secret key + host come from the
    # LANGFUSE_* env, the same way provider keys do. Idempotent if already present.
    if "langfuse_otel" not in litellm.callbacks:
        litellm.callbacks = [*litellm.callbacks, "langfuse_otel"]
    log.info("langfuse_enabled")
