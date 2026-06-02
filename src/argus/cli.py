"""The Argus CLI entrypoint: argus "your research question"."""

from __future__ import annotations

import argparse
import asyncio
import sys

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop, AgentResult
from argus.config import get_settings
from argus.llm import LLMClient
from argus.logging import configure_logging, get_logger
from argus.tools.registry import ToolRegistry
from argus.tools.web_search import register_web_search

SYSTEM_PROMPT: str = (
    "You are Argus, a careful research assistant. Use the web_search tool to find "
    "current, factual information before answering. Cite the URLs you relied on. "
    "If the tools cannot answer the question, say so plainly rather than guessing."
)


def build_loop() -> AgentLoop:
    settings = get_settings()
    registry = ToolRegistry()
    register_web_search(registry)
    return AgentLoop(
        registry=registry,
        llm=LLMClient(model=settings.model, timeout_s=settings.request_timeout_s),
        budget=Budget(
            max_turns=settings.max_turns,
            max_tokens=settings.max_tokens,
            max_wallclock_s=settings.max_wallclock_s,
            max_cost_usd=settings.max_cost_usd,
        ),
        system_prompt=SYSTEM_PROMPT,
    )


async def _run(question: str) -> int:
    result: AgentResult = await build_loop().run(question)
    sys.stdout.write(result.answer.rstrip() + "\n")
    get_logger(__name__).info(
        "done",
        stop_reason=result.stop_reason,
        turns=result.turns,
        tokens=result.tokens,
        cost_usd=result.cost_usd,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="argus", description="Ask Argus a research question.")
    parser.add_argument("question", help="The research question to answer.")
    arguments = parser.parse_args()

    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    raise SystemExit(asyncio.run(_run(arguments.question)))


if __name__ == "__main__":
    main()
