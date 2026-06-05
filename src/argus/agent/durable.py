"""Durable research orchestration via DBOS (opt-in, Postgres-checkpointed).

The in-process Orchestrator streams tokens and is ideal for the live SSE UI, but a
crash mid-run loses the work. This module runs the same plan -> search -> synthesize
-> reflect flow as a DBOS *durable workflow*: each stage is a @DBOS.step whose output
is checkpointed to Postgres, so if the process is killed and restarts, DBOS resumes
from the last completed step instead of re-paying for the whole run (steps run
at-least-once and are never re-executed once complete).

It is opt-in (ARGUS_USE_DURABLE) and leaves the in-process + ARQ/KEDA paths untouched.
The deterministic-workflow contract: all non-determinism (LLM calls, tool use, search)
lives inside steps; the workflow body only sequences them. Non-serializable resources
(the LLM client, the tool registry) are held in a module-level context — only plain
data (questions, findings) crosses step boundaries so DBOS can serialize the
checkpoints.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from dbos import DBOS, DBOSConfig

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.agent.orchestrator import (
    Finding,
    Reflection,
    ResearchClient,
    ResearchPlan,
    ResearchReport,
)
from argus.agent.prompts import (
    planner_messages,
    reflection_messages,
    research_system_prompt,
    synthesis_messages,
)
from argus.agent.sources import dedupe
from argus.config import Settings
from argus.logging import get_logger
from argus.tools.registry import ToolRegistry

log = get_logger(__name__)


@dataclass
class _Context:
    llm: ResearchClient
    registry: ToolRegistry
    searcher_budget: Budget
    ingested_sources: list[str] = field(default_factory=list)
    max_rounds: int = 2
    max_sub_questions: int = 4


# Set by configure_durable() before any workflow runs (and re-set at process start so
# recovery after a crash has the resources its steps need). The steps reach for this
# rather than receiving it as a (non-serializable) argument.
_ctx: _Context | None = None
_launched: bool = False


def _require_ctx() -> _Context:
    if _ctx is None:
        raise RuntimeError("durable orchestrator not configured; call configure_durable() first")
    return _ctx


def configure_durable(
    *,
    llm: ResearchClient,
    registry: ToolRegistry,
    searcher_budget: Budget,
    ingested_sources: list[str],
    max_rounds: int = 2,
    max_sub_questions: int = 4,
) -> None:
    global _ctx
    _ctx = _Context(
        llm=llm,
        registry=registry,
        searcher_budget=searcher_budget,
        ingested_sources=list(ingested_sources),
        max_rounds=max_rounds,
        max_sub_questions=max_sub_questions,
    )


def launch_durable(settings: Settings) -> None:
    # Idempotent process-global init: point DBOS at the same Postgres Argus already
    # runs and keep its bookkeeping tables in a dedicated schema. launch() recovers
    # any workflows left pending by a previous crash before returning.
    global _launched
    if _launched:
        return
    config: DBOSConfig = {
        "name": "argus",
        "database_url": settings.database_url,
        "system_database_url": settings.database_url,
        "dbos_system_schema": "argus_dbos",
        "log_level": "WARNING",  # DBOS is chatty at INFO (migrations, conductor banner)
    }
    DBOS(config=config)
    DBOS.launch()
    _launched = True
    log.info("durable_launched", schema="argus_dbos")


@DBOS.step()
async def _plan_step(question: str, max_sub_questions: int) -> list[str]:
    plan: ResearchPlan = await _require_ctx().llm.complete_structured(
        planner_messages(question, max_sub_questions), ResearchPlan
    )
    return plan.sub_questions[:max_sub_questions]


@DBOS.step()
async def _search_step(sub_question: str) -> dict[str, Any]:
    context = _require_ctx()
    loop = AgentLoop(
        registry=context.registry,
        llm=context.llm,
        budget=context.searcher_budget,
        system_prompt=research_system_prompt(context.ingested_sources),
    )
    result = await loop.run(sub_question)
    return Finding(
        sub_question=sub_question, answer=result.answer, sources=result.sources
    ).model_dump()


@DBOS.step()
async def _synthesize_step(question: str, findings: list[dict[str, Any]]) -> str:
    parsed: list[Finding] = [Finding.model_validate(item) for item in findings]
    sources = dedupe([source for finding in parsed for source in finding.sources])
    response = await _require_ctx().llm.complete(
        synthesis_messages(
            question, [(finding.sub_question, finding.answer) for finding in parsed], sources
        )
    )
    return response.content or ""


@DBOS.step()
async def _reflect_step(question: str, draft: str) -> dict[str, Any]:
    reflection: Reflection = await _require_ctx().llm.complete_structured(
        reflection_messages(question, draft), Reflection
    )
    return reflection.model_dump()


@DBOS.workflow()
async def research_workflow(question: str) -> dict[str, Any]:
    # Deterministic body: every LLM/tool call is inside a checkpointed step above, so
    # a resumed run replays the loop and skips whatever already completed.
    context = _require_ctx()
    pending: list[str] = await _plan_step(question, context.max_sub_questions)
    findings: list[dict[str, Any]] = []
    draft: str = ""
    rounds: int = 0

    while pending and rounds < context.max_rounds:
        rounds += 1
        log.info("durable_round", n=rounds, sub_questions=len(pending))
        round_findings: list[dict[str, Any]] = await asyncio.gather(
            *(_search_step(sub_question) for sub_question in pending)
        )
        findings.extend(round_findings)
        draft = await _synthesize_step(question, findings)
        reflection: dict[str, Any] = await _reflect_step(question, draft)
        if reflection["is_complete"]:
            break
        pending = reflection["missing"][: context.max_sub_questions]

    if not draft:
        draft = await _synthesize_step(question, findings)
    return ResearchReport(
        question=question,
        answer=draft,
        findings=[Finding.model_validate(item) for item in findings],
        rounds=rounds,
    ).model_dump()


async def run_durable(question: str) -> ResearchReport:
    handle = await DBOS.start_workflow_async(research_workflow, question)
    result: dict[str, Any] = await handle.get_result()
    return ResearchReport.model_validate(result)
