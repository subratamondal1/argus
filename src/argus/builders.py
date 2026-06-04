"""Shared construction of the tool registry, agent loop, and orchestrator.

Used by both the CLI and the web server so neither owns the wiring (and so the
two never form an import cycle).
"""

from __future__ import annotations

from argus.agent.adaptive import AdaptiveOrchestrator
from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.agent.orchestrator import Orchestrator
from argus.agent.prompts import direct_system_prompt
from argus.config import Settings, get_settings
from argus.llm import LLMClient
from argus.tools.execute_python import register_execute_python
from argus.tools.rag_search import register_rag_search
from argus.tools.registry import ToolRegistry
from argus.tools.web_fetch import register_web_fetch
from argus.tools.web_search import register_web_search


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    settings = get_settings()
    register_web_search(registry)
    register_web_fetch(registry)
    if settings.rag_enabled:
        register_rag_search(registry)
    if settings.exec_python_enabled:
        register_execute_python(registry)
    return registry


def build_budget(settings: Settings) -> Budget:
    return Budget(
        max_turns=settings.max_turns,
        max_tokens=settings.max_tokens,
        max_wallclock_s=settings.max_wallclock_s,
        max_cost_usd=settings.max_cost_usd,
    )


def build_llm(
    settings: Settings, *, model: str | None = None, temperature: float | None = None
) -> LLMClient:
    # One place wires retries + the fallback chain, so every LLM call inherits the
    # same reliability policy.
    return LLMClient(
        model=model or settings.model,
        timeout_s=settings.request_timeout_s,
        temperature=temperature,
        num_retries=settings.num_retries,
        fallbacks=settings.fallback_models,
    )


def build_loop(ingested_sources: list[str] | None = None) -> AgentLoop:
    settings = get_settings()
    return AgentLoop(
        registry=build_registry(),
        llm=build_llm(settings),
        budget=build_budget(settings),
        system_prompt=direct_system_prompt(ingested_sources),
    )


def build_orchestrator(ingested_sources: list[str] | None = None) -> Orchestrator:
    settings = get_settings()
    return Orchestrator(
        llm=build_llm(settings),
        registry=build_registry(),
        searcher_budget=build_budget(settings),
        ingested_sources=list(ingested_sources or []),
        use_queue=settings.use_queue,
        result_timeout_s=settings.queue_result_timeout_s,
    )


def build_adaptive(ingested_sources: list[str] | None = None) -> AdaptiveOrchestrator:
    settings = get_settings()
    sources: list[str] = list(ingested_sources or [])
    return AdaptiveOrchestrator(
        llm=build_llm(settings),
        build_loop=lambda: build_loop(sources),
        orchestrator=build_orchestrator(sources),
        ingested_sources=sources,
    )
