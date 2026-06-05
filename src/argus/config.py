"""Typed runtime configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET: str = "dev-insecure-secret-change-me-in-production-please"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARGUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(
        default="development", description="development | production — gates fail-fast checks."
    )

    model: str = Field(
        default="anthropic/claude-sonnet-4-6",
        description="LiteLLM model id used by the agent loop.",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description=(
            "Models LiteLLM falls back to, in order, if the primary model errors after its "
            "retries. Set ARGUS_FALLBACK_MODELS as a JSON list, e.g. "
            '["anthropic/claude-haiku-4-5","openai/gpt-5.4-mini"].'
        ),
    )
    num_retries: int = Field(
        default=2, ge=0, description="LiteLLM retries on transient failures before falling back."
    )
    judge_model: str | None = Field(
        default=None,
        description=(
            "Independent model for the eval LLM-judge. Set ARGUS_JUDGE_MODEL to a DIFFERENT "
            "provider/model than `model` to avoid self-grading bias; defaults to `model` at "
            "temperature 0, in which case the judge is trusted only via Cohen's-κ calibration."
        ),
    )
    request_timeout_s: float = Field(default=30.0, gt=0, description="Per-LLM-call timeout.")
    searxng_host: str = Field(default="localhost", description="Host where SearXNG is reachable.")
    searxng_port: int = Field(
        default=8080, gt=0, le=65535, description="Host port SearXNG is published on."
    )
    max_turns: int = Field(default=8, gt=0, description="Maximum LLM turns per run.")
    max_tokens: int = Field(default=120_000, gt=0, description="Maximum cumulative tokens per run.")
    max_wallclock_s: float = Field(
        default=180.0, gt=0, description="Maximum wall-clock seconds per run."
    )
    max_cost_usd: float = Field(default=0.50, gt=0, description="Hard cost cap per run in USD.")

    # --- Datastore + RAG (PostgreSQL + pgvector; embeddings/rerank are local) ---
    database_url: str = Field(
        default="postgresql://argus:argus@localhost:5432/argus",
        description="PostgreSQL connection URL (asyncpg).",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Native Ollama server for local embeddings and the offline LLM.",
    )
    embedding_model: str = Field(
        default="ollama/nomic-embed-text",
        description=(
            "Embedding model. An ollama/ model is served locally; anything else "
            "(e.g. openai/text-embedding-3-small) goes through LiteLLM."
        ),
    )
    embedding_dimensions: int = Field(
        default=768,
        gt=0,
        description="Output embedding width; must match the chunks.embedding vector(N) column.",
    )
    context_model: str | None = Field(
        default=None,
        description=(
            "LLM for contextual-retrieval prefixes at ingest time; defaults to `model`. "
            "Point at a local model (e.g. ollama_chat/qwen3:14b) for cheap bulk contextualization."
        ),
    )
    rerank_model: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Cross-encoder reranker, run in-process via sentence-transformers.",
    )
    rag_enabled: bool = Field(default=True, description="Register the rag_search tool.")
    rerank_enabled: bool = Field(
        default=False, description="Enable the cross-encoder rerank stage."
    )

    # --- execute_python sandbox (subprocess + rlimits; see tools/execute_python.py) ---
    exec_python_enabled: bool = Field(
        default=True, description="Register the sandboxed execute_python tool."
    )
    exec_timeout_s: float = Field(
        default=5.0,
        gt=0,
        description="Wall-clock seconds before the snippet's process group is killed.",
    )
    exec_cpu_seconds: int = Field(
        default=5, gt=0, description="RLIMIT_CPU ceiling (CPU-seconds) for the snippet process."
    )
    exec_memory_mb: int = Field(
        default=256,
        gt=0,
        description="RLIMIT_AS ceiling in MiB (Linux only; not enforced on macOS dev boxes).",
    )
    exec_file_size_mb: int = Field(
        default=10, gt=0, description="RLIMIT_FSIZE ceiling in MiB for files the snippet writes."
    )
    exec_max_processes: int = Field(
        default=16,
        gt=0,
        description="Fork headroom over the host's current per-UID process count (RLIMIT_NPROC).",
    )
    exec_max_output_chars: int = Field(
        default=10_000,
        gt=0,
        description="Per-stream cap on captured stdout/stderr returned to the model.",
    )

    # --- Searcher work queue (ARQ-on-Redis; optional, KEDA-autoscalable) ---
    use_queue: bool = Field(
        default=False,
        description=(
            "Fan searchers out as ARQ jobs on Redis (separate worker processes KEDA can "
            "autoscale) instead of in-process asyncio.gather. Set ARGUS_USE_QUEUE=true once "
            "a worker + Redis are running."
        ),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis DSN for the ARQ searcher queue (redis.asyncio under arq).",
    )
    queue_max_jobs: int = Field(
        default=10, gt=0, description="Concurrent jobs per ARQ worker process."
    )
    queue_result_timeout_s: float = Field(
        default=200.0,
        gt=0,
        description="Max seconds the orchestrator waits on one searcher Job.result().",
    )

    # --- Durable execution (DBOS; optional `durable` extra; Postgres-checkpointed) ---
    use_durable: bool = Field(
        default=False,
        description=(
            "Run deep research as a DBOS durable workflow so a crash resumes from the last "
            "completed step. Checkpoints into the existing Postgres (schema argus_dbos); "
            "needs the 'durable' extra. Leaves the in-process + ARQ/KEDA paths untouched."
        ),
    )

    # --- MCP server (registry-as-MCP; optional `mcp` extra; `argus mcp`) ---
    mcp_expose_ask: bool = Field(
        default=False,
        description=(
            "Also expose ASK-gated tools (the sandboxed execute_python) over the MCP server. "
            "Off by default — only ALLOW tools (web_search/web_fetch/rag_search) are exposed; "
            "over MCP the host owns tool-call approval."
        ),
    )

    # --- API rate limiting (Redis sliding-window; shared across API replicas) ---
    rate_limit_enabled: bool = Field(
        default=False, description="Enable the per-client Redis sliding-window rate limiter."
    )
    rate_limit_requests: int = Field(
        default=60, gt=0, description="Allowed requests per client per window."
    )
    rate_limit_window_s: float = Field(
        default=60.0, gt=0, description="Rate-limit window length in seconds."
    )

    # --- OpenTelemetry tracing (optional `otel` extra; exports to an OTLP collector) ---
    otel_enabled: bool = Field(
        default=False, description="Enable OpenTelemetry tracing (needs the 'otel' extra)."
    )
    otel_endpoint: str = Field(
        default="http://localhost:4318", description="OTLP HTTP endpoint (Jaeger/collector)."
    )
    otel_service_name: str = Field(default="argus", description="service.name on emitted spans.")

    # --- Langfuse LLM tracing (LLMOps) — keys/host via LANGFUSE_* env (LiteLLM reads them) ---
    langfuse_enabled: bool = Field(
        default=False,
        description="Route every LiteLLM call to Langfuse (set LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST).",
    )

    # --- Auth (email/password -> HS256 JWT; each user is bound to a tenant) ---
    jwt_secret: str = Field(
        default=_DEFAULT_JWT_SECRET,
        description="HS256 signing secret for auth JWTs (>=32 bytes) — MUST be overridden in prod.",
    )
    jwt_expiry_s: int = Field(
        default=86_400, gt=0, description="JWT lifetime in seconds (default 1 day)."
    )

    # --- Session cookie (httpOnly JWT carrier; CSRF-paired) — robust vs localStorage ---
    cookie_name: str = Field(
        default="argus_session",
        description=(
            "Session cookie name (carries the HS256 JWT, httpOnly). Use "
            "'__Host-argus_session' in prod ONLY when host-only (no cookie_domain) — the "
            "__Host- prefix forbids Domain."
        ),
    )
    cookie_secure: bool = Field(
        default=False,
        description=(
            "Set Secure on the session/CSRF cookies. MUST be true in prod (HTTPS); false in "
            "dev because http://localhost drops Secure cookies."
        ),
    )
    cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        description=(
            "SameSite for the cookies. 'lax' is correct for same-site dev (localhost:3000<->8000, "
            "ports don't affect site) and same-registrable-domain prod; 'none' (needs Secure) "
            "only for split-registrable-domain prod."
        ),
    )
    cookie_domain: str | None = Field(
        default=None,
        description=(
            "Cookie Domain attribute. None = host-only (tightest). Set 'argus.app' only to span "
            "app/api subdomains; incompatible with a __Host- cookie_name."
        ),
    )
    csrf_cookie_name: str = Field(
        default="argus_csrf",
        description="Non-httpOnly CSRF cookie the SPA reads and echoes back as a header.",
    )
    csrf_header_name: str = Field(
        default="X-CSRF-Token", description="Header the SPA sends carrying the CSRF token."
    )
    csrf_secret: str = Field(
        default=_DEFAULT_JWT_SECRET,
        description=(
            "HMAC key for signed double-submit CSRF tokens — MUST be overridden in prod (the "
            "same fail-fast validator as jwt_secret covers it)."
        ),
    )

    log_level: str = Field(default="INFO", description="structlog/stdlib level (e.g. DEBUG, INFO).")
    log_json: bool = Field(default=False, description="Emit JSON logs.")

    @model_validator(mode="after")
    def _require_real_jwt_secret(self) -> Self:
        # Fail fast: outside development, a JWT or CSRF secret that's the public default
        # or under 32 bytes lets anyone forge tokens (auth) or CSRF challenges. Refuse to boot.
        if self.environment == "development":
            return self
        for name, value in (
            ("ARGUS_JWT_SECRET", self.jwt_secret),
            ("ARGUS_CSRF_SECRET", self.csrf_secret),
        ):
            if value == _DEFAULT_JWT_SECRET or len(value) < 32:
                raise ValueError(
                    f"{name} must be a unique secret of at least 32 bytes outside development "
                    "(set ARGUS_ENVIRONMENT=development to allow the dev default)."
                )
        return self

    @property
    def searxng_url(self) -> str:
        return f"http://{self.searxng_host}:{self.searxng_port}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
