"""Wire the real retriever, agent loop, and judge into the eval runner.

This is the live gate: it ingests the eval corpus (the repo's own docs) into a
dedicated corpus, then runs the golden set through real retrieval, a real agent
answer, and the LLM judge. Needs the data stack and an LLM, so it runs from
`argus eval` / `make eval`, not in hermetic CI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import orjson

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.agent.prompts import research_system_prompt
from argus.config import get_settings
from argus.db import close_pool
from argus.eval.dataset import load_golden, load_thresholds
from argus.eval.judge import Verdict, judge_answer
from argus.eval.runner import EvalReport, evaluate
from argus.llm import LLMClient
from argus.logging import get_logger
from argus.rag.ingest import ingest_source
from argus.rag.retriever import RetrievedChunk, retrieve
from argus.tools.rag_search import register_rag_search
from argus.tools.registry import ToolRegistry
from argus.tools.web_fetch import register_web_fetch
from argus.tools.web_search import register_web_search

log = get_logger(__name__)

_CORPUS: str = "argus-eval"
_SOURCES: tuple[str, ...] = ("README.md", "docs/adr/0001-datastore-postgres-pgvector.md")


async def run_gate(golden_path: Path, thresholds_path: Path, report_path: Path) -> EvalReport:
    settings = get_settings()
    golden = load_golden(golden_path)
    thresholds = load_thresholds(thresholds_path)

    llm = LLMClient(model=settings.model, timeout_s=settings.request_timeout_s)
    registry = ToolRegistry()
    register_web_search(registry)
    register_web_fetch(registry)
    register_rag_search(registry, corpus=_CORPUS)
    budget = Budget(
        max_turns=settings.max_turns,
        max_tokens=settings.max_tokens,
        max_wallclock_s=settings.max_wallclock_s,
        max_cost_usd=settings.max_cost_usd,
    )

    async def _retrieve(question: str) -> list[RetrievedChunk]:
        return await retrieve(question, top_k=thresholds.k, corpus=_CORPUS)

    async def _answer(question: str) -> str:
        loop = AgentLoop(
            registry=registry, llm=llm, budget=budget, system_prompt=research_system_prompt()
        )
        result = await loop.run(question)
        return result.answer

    async def _judge(question: str, answer: str, context: str) -> Verdict:
        return await judge_answer(llm, question=question, answer=answer, context=context)

    try:
        for source in _SOURCES:
            await ingest_source(source, corpus=_CORPUS)
        report = await evaluate(
            golden, thresholds, retrieve=_retrieve, answer=_answer, judge=_judge
        )
    finally:
        await close_pool()

    data: bytes = orjson.dumps(_report_dict(report), option=orjson.OPT_INDENT_2)
    await asyncio.to_thread(report_path.write_bytes, data)
    log.info("eval_done", passed=report.passed, n=report.n, failures=report.failures)
    return report


def _report_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "n": report.n,
        "hit_at_k": report.hit_at_k,
        "precision_at_k": report.precision_at_k,
        "mrr": report.mrr,
        "judge_pass_rate": report.judge_pass_rate,
        "passed": report.passed,
        "failures": report.failures,
        "items": [
            {
                "question": item.question,
                "hit": item.hit,
                "precision": item.precision,
                "reciprocal_rank": item.reciprocal_rank,
                "judge_passed": item.judge_passed,
                "keyword_ok": item.keyword_ok,
            }
            for item in report.items
        ],
    }
