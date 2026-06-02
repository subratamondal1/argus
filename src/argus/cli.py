"""The Argus CLI entrypoint: argus "your research question"."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime

from dotenv import load_dotenv

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop, AgentResult
from argus.config import get_settings
from argus.llm import LLMClient
from argus.logging import configure_logging, get_logger
from argus.tools.registry import ToolRegistry
from argus.tools.web_fetch import register_web_fetch
from argus.tools.web_search import register_web_search


def _system_prompt() -> str:
    today: str = datetime.now().strftime("%Y-%m-%d")
    return (
        f"You are Argus, a careful research assistant. Today's date is {today}. "
        "Your workflow: call web_search to find relevant sources, then call web_fetch "
        "to read the most authoritative result before answering. Search snippets are "
        "often stale or incomplete, so verify claims against fetched page content. "
        "For 'latest' or 'most recent' questions, be skeptical: a single announcement "
        "page often calls itself 'our latest' even when a newer one exists, so prefer "
        "a comprehensive overview, listing, or changelog page, cross-check at least two "
        "sources, and choose the one with the newest date or the highest version number. "
        "Cite the URLs you relied on. If the tools cannot answer, say so plainly rather "
        "than guessing."
    )


def build_loop() -> AgentLoop:
    settings = get_settings()
    registry = ToolRegistry()
    register_web_search(registry)
    register_web_fetch(registry)
    return AgentLoop(
        registry=registry,
        llm=LLMClient(model=settings.model, timeout_s=settings.request_timeout_s),
        budget=Budget(
            max_turns=settings.max_turns,
            max_tokens=settings.max_tokens,
            max_wallclock_s=settings.max_wallclock_s,
            max_cost_usd=settings.max_cost_usd,
        ),
        system_prompt=_system_prompt(),
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
    load_dotenv()
    parser = argparse.ArgumentParser(prog="argus", description="Ask Argus a research question.")
    parser.add_argument("question", help="The research question to answer.")
    arguments = parser.parse_args()

    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    raise SystemExit(asyncio.run(_run(arguments.question)))


if __name__ == "__main__":
    main()
