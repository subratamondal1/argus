"""The Argus CLI entrypoint: argus "your research question" [--deep]."""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.agent.orchestrator import Orchestrator
from argus.agent.prompts import research_system_prompt
from argus.config import Settings, get_settings
from argus.llm import LLMClient
from argus.logging import configure_logging, get_logger
from argus.tools.registry import ToolRegistry
from argus.tools.web_fetch import register_web_fetch
from argus.tools.web_search import register_web_search


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_web_search(registry)
    register_web_fetch(registry)
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


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="argus", description="Ask Argus a research question.")
    parser.add_argument("question", help="The research question to answer.")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Use the multi-agent orchestrator (plan, search, synthesize, reflect).",
    )
    arguments = parser.parse_args()

    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    raise SystemExit(asyncio.run(_run(arguments.question, deep=arguments.deep)))


if __name__ == "__main__":
    main()
