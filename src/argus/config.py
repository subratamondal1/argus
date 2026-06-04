"""Typed runtime configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARGUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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

    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False, description="Emit JSON logs.")

    @property
    def searxng_url(self) -> str:
        return f"http://{self.searxng_host}:{self.searxng_port}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
