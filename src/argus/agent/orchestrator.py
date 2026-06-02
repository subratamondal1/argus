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
from dataclasses import dataclass
from typing import Any, Protocol

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
from argus.llm import LLMResponse
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

    async def run(self, question: str, *, on_event: EventSink | None = None) -> ResearchReport:
        plan: ResearchPlan = await self.llm.complete_structured(
            planner_messages(question, self.max_sub_questions), ResearchPlan
        )
        pending: list[str] = plan.sub_questions[: self.max_sub_questions]
        await emit(on_event, "plan", sub_questions=pending)
        findings: list[Finding] = []
        draft: str = ""
        rounds: int = 0

        while pending and rounds < self.max_rounds:
            rounds += 1
            log.info("research_round", n=rounds, sub_questions=len(pending))
            round_findings: list[Finding] = await asyncio.gather(
                *(self._search(sub_question, on_event) for sub_question in pending)
            )
            findings.extend(round_findings)
            await emit(on_event, "synthesize", findings=len(findings))
            draft = await self._synthesize(question, findings)
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
            draft = await self._synthesize(question, findings)
        log.info("research_done", rounds=rounds, findings=len(findings))
        await emit(on_event, "answer", text=draft)
        return ResearchReport(question=question, answer=draft, findings=findings, rounds=rounds)

    async def _search(self, sub_question: str, on_event: EventSink | None = None) -> Finding:
        await emit(on_event, "search_start", sub_question=sub_question)
        loop = AgentLoop(
            registry=self.registry,
            llm=self.llm,
            budget=self.searcher_budget,
            system_prompt=research_system_prompt(),
        )
        result = await loop.run(sub_question, on_event=_tagged(on_event, sub_question))
        await emit(on_event, "search_done", sub_question=sub_question)
        return Finding(sub_question=sub_question, answer=result.answer)

    async def _synthesize(self, question: str, findings: list[Finding]) -> str:
        response: LLMResponse = await self.llm.complete(
            synthesis_messages(question, [(f.sub_question, f.answer) for f in findings])
        )
        return response.content or ""
