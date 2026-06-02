"""The Argus CLI entrypoint: argus "your research question" [--deep]."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.agent.orchestrator import Orchestrator
from argus.agent.prompts import research_system_prompt
from argus.config import Settings, get_settings
from argus.db import close_pool
from argus.eval.harness import run_gate
from argus.eval.runner import EvalReport
from argus.llm import LLMClient
from argus.logging import configure_logging, get_logger
from argus.rag.ingest import ingest_source
from argus.tools.rag_search import register_rag_search
from argus.tools.registry import ToolRegistry
from argus.tools.web_fetch import register_web_fetch
from argus.tools.web_search import register_web_search


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_web_search(registry)
    register_web_fetch(registry)
    if get_settings().rag_enabled:
        register_rag_search(registry)
    return registry


def _budget(settings: Settings) -> Budget:
    return Budget(
        max_turns=settings.max_turns,
        max_tokens=settings.max_tokens,
        max_wallclock_s=settings.max_wallclock_s,
        max_cost_usd=settings.max_cost_usd,
    )


def build_loop() -> AgentLoop:
    settings = get_settings()
    return AgentLoop(
        registry=_registry(),
        llm=LLMClient(model=settings.model, timeout_s=settings.request_timeout_s),
        budget=_budget(settings),
        system_prompt=research_system_prompt(),
    )


def build_orchestrator() -> Orchestrator:
    settings = get_settings()
    return Orchestrator(
        llm=LLMClient(model=settings.model, timeout_s=settings.request_timeout_s),
        registry=_registry(),
        searcher_budget=_budget(settings),
    )


async def _run(question: str, *, deep: bool) -> int:
    log = get_logger(__name__)
    if deep:
        report = await build_orchestrator().run(question)
        sys.stdout.write(report.answer.rstrip() + "\n")
        log.info("done", mode="deep", rounds=report.rounds, findings=len(report.findings))
    else:
        result = await build_loop().run(question)
        sys.stdout.write(result.answer.rstrip() + "\n")
        log.info(
            "done",
            mode="single",
            stop_reason=result.stop_reason,
            turns=result.turns,
            tokens=result.tokens,
            cost_usd=result.cost_usd,
        )
    return 0


async def _run_ingest(source: str, *, corpus: str, corpus_version: str) -> int:
    log = get_logger(__name__)
    try:
        result = await ingest_source(source, corpus=corpus, corpus_version=corpus_version)
    finally:
        await close_pool()
    sys.stdout.write(f"ingested {result.chunks_written} chunks from {result.source_uri}\n")
    log.info("done", mode="ingest", source=result.source_uri, chunks=result.chunks_written)
    return 0


def _main_ask(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="argus", description="Ask Argus a research question.")
    parser.add_argument("question", help="The research question to answer.")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Use the multi-agent orchestrator (plan, search, synthesize, reflect).",
    )
    arguments = parser.parse_args(argv)
    return asyncio.run(_run(arguments.question, deep=arguments.deep))


def _main_ingest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="argus ingest", description="Ingest a document (path or URL) into the local corpus."
    )
    parser.add_argument("source", help="A file path or URL to ingest.")
    parser.add_argument("--corpus", default="default", help="Corpus name to ingest into.")
    parser.add_argument("--corpus-version", default="v1", help="Corpus version tag.")
    arguments = parser.parse_args(argv)
    return asyncio.run(
        _run_ingest(
            arguments.source, corpus=arguments.corpus, corpus_version=arguments.corpus_version
        )
    )


def _format_eval(report: EvalReport) -> str:
    status: str = "PASS" if report.passed else "FAIL"
    lines: list[str] = [
        f"eval {status}  (n={report.n})",
        f"  hit@k           {report.hit_at_k:.3f}",
        f"  precision@k     {report.precision_at_k:.3f}",
        f"  mrr             {report.mrr:.3f}",
        f"  judge_pass_rate {report.judge_pass_rate:.3f}",
    ]
    lines.extend(f"  - {failure}" for failure in report.failures)
    return "\n".join(lines) + "\n"


def _main_eval(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="argus eval", description="Run the golden-set eval gate against the live stack."
    )
    parser.add_argument("--golden", default="eval/golden.jsonl", help="Golden dataset (jsonl).")
    parser.add_argument("--thresholds", default="eval/thresholds.json", help="Gate thresholds.")
    parser.add_argument(
        "--report", default="eval/last_report.json", help="Where to write the report."
    )
    arguments = parser.parse_args(argv)
    report = asyncio.run(
        run_gate(Path(arguments.golden), Path(arguments.thresholds), Path(arguments.report))
    )
    sys.stdout.write(_format_eval(report))
    return 0 if report.passed else 1


def main() -> None:
    load_dotenv()
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    argv: list[str] = sys.argv[1:]
    if argv and argv[0] == "ingest":
        raise SystemExit(_main_ingest(argv[1:]))
    if argv and argv[0] == "eval":
        raise SystemExit(_main_eval(argv[1:]))
    raise SystemExit(_main_ask(argv))


if __name__ == "__main__":
    main()
