"""ARQ worker: the searcher fan-out as separate, KEDA-autoscalable processes.

Phase 4 lifts the orchestrator's in-process searcher fan-out (asyncio.gather over
AgentLoop coroutines) onto an ARQ-on-Redis work queue. The orchestrator enqueues
one ``search_subquestion`` job per sub-question and awaits each Job's result; the
jobs run here, in a pool of ``arq`` worker processes that Kubernetes (via KEDA's
Redis-list scaler on the queue key) scales out under load.

The agent logic is unchanged by the move: each job rebuilds the same registry +
LLM + budget the in-process path used and runs one AgentLoop. The only new
concern is context — a job runs in a fresh process with its own event loop, so the
request_id / run_id bound to structlog contextvars on the HTTP side do NOT follow.
They are passed as job kwargs and re-bound at the top of the task, so a single
request_id still threads HTTP request -> enqueue -> worker.
"""

from __future__ import annotations

from typing import Any, ClassVar

import structlog
from arq import func
from arq.connections import ArqRedis, RedisSettings, create_pool

from argus.agent.loop import AgentLoop
from argus.agent.prompts import research_system_prompt
from argus.builders import build_budget, build_llm, build_registry
from argus.config import Settings, get_settings
from argus.logging import configure_logging, get_logger

log = get_logger(__name__)

# The Redis list key ARQ pushes queued jobs onto. KEDA's redis scaler watches this
# key's length to size the worker pool, so it is pinned (not left to arq's default)
# to keep the producer pool, the worker, and the scaler config in lock-step — a
# producer/worker queue-name mismatch is the single most common silent ARQ bug.
QUEUE_NAME: str = "arq:queue:searchers"

# arq stores its queue as a Redis SORTED SET, but KEDA's redis scaler measures
# depth with LLEN (lists only) — LLEN on a zset raises WRONGTYPE. So the producer
# also LPUSHes a marker per enqueued job onto this plain LIST, and a worker LREMs
# its marker when it picks the job up. KEDA scales on LLEN of this list: a
# best-effort backlog signal (a leaked marker only keeps one extra pod briefly),
# decoupled from arq's own at-least-once correctness.
SCALE_LIST: str = "argus:searcher:scale"


def redis_settings(settings: Settings | None = None) -> RedisSettings:
    resolved: Settings = settings or get_settings()
    return RedisSettings.from_dsn(resolved.redis_url)


async def search_subquestion(
    ctx: dict[str, Any],
    sub_question: str,
    *,
    ingested_sources: list[str],
    _request_id: str = "",
    _run_id: str = "",
) -> dict[str, Any]:
    # Re-bind the correlation ids the HTTP side passed in: this process has a fresh
    # event loop and empty contextvars, so without this every worker log line would
    # be untraceable back to the originating request/run.
    structlog.contextvars.bind_contextvars(request_id=_request_id, run_id=_run_id)
    try:
        # This job is now being processed, so drop its KEDA backlog marker. arq
        # supplies ctx['redis']; guard it so the unit tests (no redis in ctx) skip.
        redis: Any = ctx.get("redis")
        job_id: Any = ctx.get("job_id")
        if redis is not None and job_id is not None:
            await redis.lrem(SCALE_LIST, 0, job_id)
        log.info("search_job_start", sub_question=sub_question, job_id=job_id)
        loop: AgentLoop = AgentLoop(
            registry=ctx["registry"],
            llm=ctx["llm"],
            budget=ctx["budget"],
            system_prompt=research_system_prompt(ingested_sources),
        )
        result = await loop.run(sub_question)
        log.info(
            "search_job_done",
            sub_question=sub_question,
            turns=result.turns,
            cost_usd=result.cost_usd,
            sources=len(result.sources),
        )
        # Return a plain JSON-safe dict, not a Pydantic instance: arq pickles the
        # result into Redis, and a dict keeps the wire contract explicit and
        # version-tolerant. The orchestrator rehydrates it into a Finding.
        return {
            "sub_question": sub_question,
            "answer": result.answer,
            "sources": [source.model_dump() for source in result.sources],
        }
    finally:
        structlog.contextvars.unbind_contextvars("request_id", "run_id")


async def _startup(ctx: dict[str, Any]) -> None:
    # Built once per worker process (not per job) so the LiteLLM client, tool
    # registry, and budget template are reused across every job the worker runs.
    settings: Settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    ctx["registry"] = build_registry()
    ctx["llm"] = build_llm(settings)
    ctx["budget"] = build_budget(settings)
    log.info("worker_startup", model=settings.model, queue=QUEUE_NAME)


async def _shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker_shutdown")


class WorkerSettings:
    """ARQ worker entrypoint: ``uv run arq argus.worker.WorkerSettings``."""

    redis_settings: RedisSettings = redis_settings()
    queue_name: str = QUEUE_NAME
    functions: ClassVar[list[Any]] = [func(search_subquestion, name="search_subquestion")]
    on_startup = _startup
    on_shutdown = _shutdown
    max_jobs: int = get_settings().queue_max_jobs
    # A searcher runs several LLM turns; give it the run's wall-clock budget plus
    # headroom so arq's own job timeout never fires before the agent's does.
    job_timeout: int = int(get_settings().max_wallclock_s) + 30
    # Results must outlive the orchestrator's await through a slow synthesize round.
    keep_result: int = 900
    # Refresh the arq health-check key often enough that `arq ... --check` (the
    # pod liveness probe) reflects a live worker within a probe period.
    health_check_interval: int = 30
    # Searchers are idempotent reads (web_search/web_fetch/rag_search have no side
    # effects), so a retry after a transient worker crash is safe.
    retry_jobs: bool = True
    max_tries: int = 2


async def create_searcher_pool(settings: Settings | None = None) -> ArqRedis:
    # default_queue_name pinned to QUEUE_NAME so enqueues land on the same list the
    # worker (and KEDA) watch.
    resolved: Settings = settings or get_settings()
    return await create_pool(redis_settings(resolved), default_queue_name=QUEUE_NAME)
