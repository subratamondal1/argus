from __future__ import annotations

from typing import Any

from argus.agent.budget import Budget
from argus.agent.orchestrator import Orchestrator, Reflection, ResearchPlan
from argus.llm import LLMResponse
from argus.tools.registry import ToolRegistry


class FakeResearchLLM:
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        on_token: Any = None,
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


async def test_orchestrator_plans_searches_and_synthesizes() -> None:
    orchestrator = Orchestrator(
        llm=FakeResearchLLM(), registry=ToolRegistry(), searcher_budget=_budget()
    )
    report = await orchestrator.run("What is the latest model?")

    assert report.answer == "FINAL SYNTHESIZED ANSWER"
    assert report.rounds == 1
    assert len(report.findings) == 2
    assert {finding.sub_question for finding in report.findings} == {"sub one", "sub two"}
    assert all(finding.answer == "a sub-finding" for finding in report.findings)


class ReplanningLLM(FakeResearchLLM):
    def __init__(self) -> None:
        self._reflections = 0

    async def complete_structured(self, messages: list[dict[str, Any]], schema: type[Any]) -> Any:
        if schema is ResearchPlan:
            return ResearchPlan(sub_questions=["only one"])
        self._reflections += 1
        if self._reflections == 1:
            return Reflection(is_complete=False, missing=["follow up"])
        return Reflection(is_complete=True, missing=[])


async def test_orchestrator_replans_when_incomplete() -> None:
    orchestrator = Orchestrator(
        llm=ReplanningLLM(), registry=ToolRegistry(), searcher_budget=_budget()
    )
    report = await orchestrator.run("What is the latest model?")

    assert report.rounds == 2
    assert len(report.findings) == 2
