"""In-process research orchestrator: plan, fan out searchers, synthesize, reflect.

This is the orchestrator-worker pattern run in a single process: a planner
decomposes the question into independent sub-questions, a fan-out of searcher
agents (each its own AgentLoop with isolated context) answers them in parallel,
a synthesizer fuses the findings, and a reflection step decides whether to
replan another round. Phase 2b lifts the searcher fan-out onto an ARQ-on-Redis
work queue so the workers can scale out as Kubernetes pods; the logic here is
unchanged by that move.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from pydantic import BaseModel, Field

from argus.agent.budget import Budget
from argus.agent.events import AgentEvent, EventSink, emit
from argus.agent.loop import AgentLoop
from argus.agent.prompts import (
    planner_messages,
    reflection_messages,
    research_system_prompt,
    synthesis_messages,
)
from argus.agent.sources import Source, dedupe, numbered_payload
from argus.llm import LLMResponse, TokenSink
from argus.logging import get_logger
from argus.tools.registry import ToolRegistry

log = get_logger(__name__)


def _tagged(sink: EventSink | None, sub_question: str) -> EventSink | None:
    if sink is None:
        return None

    async def wrapped(event: AgentEvent) -> None:
        await sink(AgentEvent(event.kind, {**event.data, "sub_question": sub_question}))

    return wrapped


class ResearchPlan(BaseModel):
    sub_questions: list[str] = Field(description="Independent sub-questions to research.")


class Reflection(BaseModel):
    is_complete: bool = Field(
        description="Whether the draft fully and correctly answers the question."
    )
    missing: list[str] = Field(description="Follow-up sub-questions if not complete, else empty.")


class Finding(BaseModel):
    sub_question: str
    answer: str
    sources: list[Source] = Field(default_factory=list)


class ResearchReport(BaseModel):
    question: str
    answer: str
    findings: list[Finding]
    rounds: int


class ResearchClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        on_token: TokenSink | None = None,
    ) -> LLMResponse: ...

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type[Any]
    ) -> Any: ...


@dataclass
class Orchestrator:
    llm: ResearchClient
    registry: ToolRegistry
    searcher_budget: Budget
    max_rounds: int = 2
    max_sub_questions: int = 4
    ingested_sources: list[str] = field(default_factory=list)
    use_queue: bool = False
    result_timeout_s: float = 200.0
    _pool: Any = field(default=None, init=False, repr=False)

    async def run(self, question: str, *, on_event: EventSink | None = None) -> ResearchReport:
        plan: ResearchPlan = await self.llm.complete_structured(
            planner_messages(question, self.max_sub_questions), ResearchPlan
        )
        return await self.research(question, plan.sub_questions, on_event=on_event)

    async def research(
        self, question: str, sub_questions: list[str], *, on_event: EventSink | None = None
    ) -> ResearchReport:
        pending: list[str] = sub_questions[: self.max_sub_questions]
        await emit(on_event, "plan", sub_questions=pending)
        findings: list[Finding] = []
        collected: list[Source] = []
        draft: str = ""
        rounds: int = 0

        while pending and rounds < self.max_rounds:
            rounds += 1
            log.info("research_round", n=rounds, sub_questions=len(pending))
            round_findings: list[Finding] = await asyncio.gather(
                *(self._search(sub_question, on_event) for sub_question in pending)
            )
            findings.extend(round_findings)
            for finding in round_findings:
                collected.extend(finding.sources)
            sources: list[Source] = dedupe(collected)
            await emit(on_event, "sources", items=numbered_payload(sources))
            await emit(on_event, "synthesize", findings=len(findings))
            draft = await self._synthesize(question, findings, sources, on_event)
            # Signal that self-verification is starting BEFORE the (non-streaming)
            # reflection call, so the UI can show "verifying/refining" during the
            # gap instead of looking stalled while the draft sits there.
            await emit(on_event, "review")
            reflection: Reflection = await self.llm.complete_structured(
                reflection_messages(question, draft), Reflection
            )
            await emit(
                on_event, "reflect", complete=reflection.is_complete, missing=reflection.missing
            )
            if reflection.is_complete:
                break
            pending = reflection.missing[: self.max_sub_questions]

        if not draft:
            sources = dedupe(collected)
            await emit(on_event, "sources", items=numbered_payload(sources))
            await emit(on_event, "synthesize", findings=len(findings))
            draft = await self._synthesize(question, findings, sources, on_event)
        log.info("research_done", rounds=rounds, findings=len(findings))
        await emit(on_event, "answer", text=draft)
        return ResearchReport(question=question, answer=draft, findings=findings, rounds=rounds)

    async def _search(self, sub_question: str, on_event: EventSink | None = None) -> Finding:
        if self.use_queue:
            return await self._search_queued(sub_question, on_event)
        return await self._search_inproc(sub_question, on_event)

    async def _search_inproc(self, sub_question: str, on_event: EventSink | None = None) -> Finding:
        await emit(on_event, "search_start", sub_question=sub_question)
        loop = AgentLoop(
            registry=self.registry,
            llm=self.llm,
            budget=self.searcher_budget,
            system_prompt=research_system_prompt(self.ingested_sources),
        )
        result = await loop.run(sub_question, on_event=_tagged(on_event, sub_question))
        await emit(on_event, "search_done", sub_question=sub_question)
        return Finding(sub_question=sub_question, answer=result.answer, sources=result.sources)

    async def _get_pool(self) -> Any:
        if self._pool is None:
            # Lazy import keeps arq out of the in-process path's import graph, so it
            # stays an optional runtime dependency for users who don't run the queue.
            from argus.worker import create_searcher_pool

            self._pool = await create_searcher_pool()
        return self._pool

    async def _search_queued(self, sub_question: str, on_event: EventSink | None = None) -> Finding:
        await emit(on_event, "search_start", sub_question=sub_question)
        # Read the correlation ids while they are still bound on the HTTP side: a
        # worker job runs in a fresh process with empty contextvars, so they must
        # cross the boundary as explicit job kwargs (re-bound inside the task).
        bound: dict[str, Any] = structlog.contextvars.get_contextvars()
        request_id: str = bound.get("request_id", "")
        run_id: str = bound.get("run_id", "")
        pool: Any = await self._get_pool()
        # Unique _job_id per sub-question: arq dedupes by job id and returns None for
        # a duplicate, which would silently drop a searcher the orchestrator then
        # awaits forever. A uuid guarantees a Job back from every enqueue.
        job: Any = await pool.enqueue_job(
            "search_subquestion",
            sub_question,
            ingested_sources=self.ingested_sources,
            _request_id=request_id,
            _run_id=run_id,
            _job_id=f"searcher-{run_id or 'norun'}-{uuid.uuid4().hex}",
        )
        if job is None:
            raise RuntimeError("failed to enqueue searcher job (duplicate job id)")
        payload: dict[str, Any] = await job.result(timeout=self.result_timeout_s)
        await emit(on_event, "search_done", sub_question=sub_question)
        return Finding(
            sub_question=payload["sub_question"],
            answer=payload["answer"],
            sources=[Source.model_validate(item) for item in payload["sources"]],
        )

    async def _synthesize(
        self,
        question: str,
        findings: list[Finding],
        sources: list[Source],
        on_event: EventSink | None = None,
    ) -> str:
        token_sink: TokenSink | None = None
        if on_event is not None:

            async def token_sink(delta: str) -> None:
                await emit(on_event, "token", text=delta)

        response: LLMResponse = await self.llm.complete(
            synthesis_messages(question, [(f.sub_question, f.answer) for f in findings], sources),
            on_token=token_sink,
        )
        return response.content or ""
