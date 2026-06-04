"""Orchestrator queue path: enqueue -> worker runs task -> await result.

Two layers:
  * Unit (default): a FakePool stub stands in for ArqRedis. It runs the real
    `search_subquestion` task inline and returns a Job-like handle whose .result()
    yields the task's dict. Exercises the orchestrator's enqueue/await/rehydrate
    logic AND request_id/run_id propagation — with zero Redis, deterministic.
  * Integration (-m integration): a real arq Worker over fakeredis, proving the
    actual arq serialize -> Redis -> deserialize -> result round-trips.
"""

from __future__ import annotations

from typing import Any

import pytest
import structlog

from argus.agent.budget import Budget
from argus.agent.orchestrator import Finding, Orchestrator, Reflection, ResearchPlan
from argus.llm import LLMResponse
from argus.tools.registry import ToolRegistry


class FakeResearchLLM:
    async def complete(
        self, messages: list[dict[str, Any]], tools: Any = None, *, on_token: Any = None
    ) -> LLMResponse:
        system = str(messages[0]["content"]) if messages else ""
        content = "FINAL SYNTHESIZED ANSWER" if "synthesis" in system.lower() else "a sub-finding"
        return LLMResponse(
            content=content, tool_calls=[], prompt_tokens=5, completion_tokens=5, cost_usd=0.0
        )

    async def complete_structured(self, messages: list[dict[str, Any]], schema: type[Any]) -> Any:
        if schema is ResearchPlan:
            return ResearchPlan(sub_questions=["sub one", "sub two"])
        return Reflection(is_complete=True, missing=[])


def _budget() -> Budget:
    return Budget(max_turns=4, max_tokens=10**6, max_wallclock_s=60.0, max_cost_usd=10.0)


class _FakeJob:
    def __init__(self, payload: dict[str, Any], job_id: str) -> None:
        self._payload = payload
        self.job_id = job_id

    async def result(self, timeout: float | None = None) -> dict[str, Any]:  # noqa: ASYNC109 — mirrors arq Job.result(timeout=...)
        return self._payload


class _FakePool:
    """Stands in for ArqRedis: runs the real task inline, records kwargs seen."""

    def __init__(self) -> None:
        self.captured: list[dict[str, Any]] = []
        self.scale_pushes: list[Any] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> _FakeJob:
        from argus.worker import search_subquestion

        self.captured.append({"function": function, "args": args, "kwargs": dict(kwargs)})
        job_id: str = kwargs.get("_job_id", "fake")
        ctx: dict[str, Any] = {
            "job_id": job_id,
            "registry": ToolRegistry(),
            "llm": FakeResearchLLM(),
            "budget": _budget(),
        }
        payload: dict[str, Any] = await search_subquestion(
            ctx,
            args[0],
            ingested_sources=kwargs.get("ingested_sources", []),
            _request_id=kwargs.get("_request_id", ""),
            _run_id=kwargs.get("_run_id", ""),
        )
        return _FakeJob(payload, job_id)

    async def lpush(self, key: str, *values: Any) -> None:
        self.scale_pushes.extend(values)


async def test_queued_orchestrator_enqueues_and_awaits_results() -> None:
    pool = _FakePool()
    orch = Orchestrator(
        llm=FakeResearchLLM(), registry=ToolRegistry(), searcher_budget=_budget(), use_queue=True
    )
    orch._pool = pool  # inject the fake; bypasses create_searcher_pool / Redis

    report = await orch.run("What is the latest model?")

    assert report.answer == "FINAL SYNTHESIZED ANSWER"
    assert len(report.findings) == 2
    assert {finding.sub_question for finding in report.findings} == {"sub one", "sub two"}
    assert all(isinstance(finding, Finding) for finding in report.findings)
    assert len(pool.captured) == 2
    job_ids = {capture["kwargs"]["_job_id"] for capture in pool.captured}
    assert len(job_ids) == 2  # one job per sub-question, each with a unique id
    assert len(pool.scale_pushes) == 2  # one KEDA backlog marker LPUSHed per job


async def test_queued_orchestrator_propagates_request_and_run_id() -> None:
    pool = _FakePool()
    orch = Orchestrator(
        llm=FakeResearchLLM(), registry=ToolRegistry(), searcher_budget=_budget(), use_queue=True
    )
    orch._pool = pool

    structlog.contextvars.bind_contextvars(request_id="req_abc123", run_id="run_xyz789")
    try:
        await orch.run("anything")
    finally:
        structlog.contextvars.unbind_contextvars("request_id", "run_id")

    for capture in pool.captured:
        assert capture["kwargs"]["_request_id"] == "req_abc123"
        assert capture["kwargs"]["_run_id"] == "run_xyz789"
        assert capture["kwargs"]["_job_id"].startswith("searcher-run_xyz789-")


@pytest.mark.integration
async def test_real_arq_worker_round_trips_a_job() -> None:
    # Proves the genuine arq serialize -> Redis -> worker -> result path against a
    # REAL Redis (CI provides one via a service container; skipped when absent).
    import redis.asyncio as aioredis
    from arq import Worker
    from arq.connections import RedisSettings

    from argus.config import get_settings
    from argus.worker import QUEUE_NAME, create_searcher_pool, search_subquestion

    settings = get_settings()
    probe = aioredis.from_url(settings.redis_url)
    try:
        await probe.ping()
    except Exception:  # any connection failure means "no Redis here"
        pytest.skip(f"no Redis reachable at {settings.redis_url}")
    finally:
        await probe.aclose()

    async def _startup(ctx: dict[str, Any]) -> None:
        ctx["registry"] = ToolRegistry()
        ctx["llm"] = FakeResearchLLM()
        ctx["budget"] = _budget()

    pool = await create_searcher_pool()
    try:
        job = await pool.enqueue_job("search_subquestion", "a sub-question", ingested_sources=[])
        assert job is not None
        worker = Worker(
            functions=[search_subquestion],
            redis_settings=RedisSettings.from_dsn(settings.redis_url),
            queue_name=QUEUE_NAME,
            on_startup=_startup,
            keep_result=60,
            burst=True,
        )
        await worker.run_check()
        payload = await job.result(timeout=5)
    finally:
        await pool.aclose()

    assert payload["sub_question"] == "a sub-question"
    assert payload["answer"] == "a sub-finding"
