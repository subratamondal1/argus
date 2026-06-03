from __future__ import annotations

from typing import Any

from argus.agent.adaptive import AdaptiveOrchestrator, Strategy, Triage
from argus.agent.events import EventSink
from argus.agent.loop import AgentResult
from argus.agent.orchestrator import ResearchReport


class _FakeLLM:
    def __init__(self, triage: Triage) -> None:
        self._triage = triage

    async def complete_structured(self, messages: list[dict[str, Any]], schema: type[Any]) -> Any:
        return self._triage


class _FakeLoop:
    async def run(
        self, user_input: str, *, on_event: Any = None, stream_tokens: bool = False
    ) -> AgentResult:
        return AgentResult(
            answer="direct answer",
            stop_reason="completed",
            turns=1,
            tokens=1,
            cost_usd=0.0,
            transcript=[],
        )


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.research_called_with: list[str] | None = None
        self.run_called: bool = False

    async def run(self, question: str, *, on_event: EventSink | None = None) -> ResearchReport:
        self.run_called = True
        return ResearchReport(question=question, answer="planned report", findings=[], rounds=1)

    async def research(
        self, question: str, sub_questions: list[str], *, on_event: EventSink | None = None
    ) -> ResearchReport:
        self.research_called_with = sub_questions
        return ResearchReport(question=question, answer="research report", findings=[], rounds=1)


def _adaptive(triage: Triage, orchestrator: _FakeOrchestrator) -> AdaptiveOrchestrator:
    return AdaptiveOrchestrator(
        llm=_FakeLLM(triage), build_loop=lambda: _FakeLoop(), orchestrator=orchestrator
    )


async def test_direct_strategy_answers_with_a_single_loop() -> None:
    orchestrator = _FakeOrchestrator()
    adaptive = _adaptive(Triage(strategy=Strategy.DIRECT, reasoning="simple"), orchestrator)
    report = await adaptive.run("hi there")
    assert report.answer == "direct answer"
    assert orchestrator.research_called_with is None
    assert orchestrator.run_called is False


async def test_research_strategy_feeds_triage_subquestions_to_the_orchestrator() -> None:
    orchestrator = _FakeOrchestrator()
    adaptive = _adaptive(
        Triage(strategy=Strategy.RESEARCH, reasoning="multi-faceted", sub_questions=["q1", "q2"]),
        orchestrator,
    )
    report = await adaptive.run("research company X")
    assert report.answer == "research report"
    assert orchestrator.research_called_with == ["q1", "q2"]


async def test_force_research_skips_triage_and_plans() -> None:
    orchestrator = _FakeOrchestrator()
    adaptive = _adaptive(
        Triage(strategy=Strategy.DIRECT, reasoning="would-be-direct"), orchestrator
    )
    report = await adaptive.run("anything", force_research=True)
    assert report.answer == "planned report"
    assert orchestrator.run_called is True
