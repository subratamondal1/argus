"""Adaptive orchestration: triage each request to direct-answer or deep research.

Argus does not run a fixed mode. A cheap triage step decides, per request,
whether one agent loop can answer it directly, or whether it should be
decomposed into parallel sub-questions, researched, synthesized, and reflected
on — the router + orchestrator-workers pattern (Anthropic, "Building Effective
Agents"). The triage doubles as the planner: when it picks research it returns
the sub-questions, so no separate planning round is needed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from argus.agent.events import EventSink, emit
from argus.agent.loop import AgentResult
from argus.agent.orchestrator import ResearchReport
from argus.agent.prompts import triage_messages
from argus.agent.sources import dedupe, numbered_payload
from argus.logging import get_logger

log = get_logger(__name__)


class TriageClient(Protocol):
    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type[Any]
    ) -> Any: ...


class LoopRunner(Protocol):
    async def run(
        self,
        user_input: str,
        *,
        on_event: EventSink | None = None,
        stream_tokens: bool = False,
    ) -> AgentResult: ...


class ResearchRunner(Protocol):
    async def run(self, question: str, *, on_event: EventSink | None = None) -> ResearchReport: ...

    async def research(
        self, question: str, sub_questions: list[str], *, on_event: EventSink | None = None
    ) -> ResearchReport: ...


class Strategy(StrEnum):
    DIRECT = "direct"
    RESEARCH = "research"


class Triage(BaseModel):
    strategy: Strategy = Field(
        description="direct for simple/single questions; research for multi-faceted ones."
    )
    reasoning: str = Field(description="One sentence on why this strategy fits the request.")
    sub_questions: list[str] = Field(
        default_factory=list, description="3-5 independent sub-questions if research, else empty."
    )


@dataclass
class AdaptiveOrchestrator:
    llm: TriageClient
    build_loop: Callable[[], LoopRunner]
    orchestrator: ResearchRunner
    max_sub_questions: int = 5
    ingested_sources: list[str] = field(default_factory=list)

    async def run(
        self, question: str, *, on_event: EventSink | None = None, force_research: bool = False
    ) -> ResearchReport:
        if force_research:
            await emit(
                on_event,
                "triage",
                strategy="research",
                reasoning="Deep research requested.",
                sub_questions=[],
            )
            report = await self.orchestrator.run(question, on_event=on_event)
            await _emit_report_artifact(on_event, report)
            return report

        triage: Triage = await self.llm.complete_structured(
            triage_messages(question, self.max_sub_questions, self.ingested_sources), Triage
        )
        log.info("triage", strategy=triage.strategy.value, n=len(triage.sub_questions))
        await emit(
            on_event,
            "triage",
            strategy=triage.strategy.value,
            reasoning=triage.reasoning,
            sub_questions=triage.sub_questions,
        )

        if triage.strategy is Strategy.RESEARCH:
            if triage.sub_questions:
                report = await self.orchestrator.research(
                    question, triage.sub_questions, on_event=on_event
                )
            else:
                report = await self.orchestrator.run(question, on_event=on_event)
            await _emit_report_artifact(on_event, report)
            return report

        result = await self.build_loop().run(question, on_event=on_event, stream_tokens=True)
        sources = dedupe(result.sources)
        if sources:
            await emit(on_event, "sources", items=numbered_payload(sources))
        await emit(on_event, "answer", text=result.answer)
        return ResearchReport(question=question, answer=result.answer, findings=[], rounds=0)


async def _emit_report_artifact(on_event: EventSink | None, report: ResearchReport) -> None:
    if report.answer.strip():
        await emit(
            on_event, "artifact", title="Research report", kind="report", content=report.answer
        )
