from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("dbos")  # the durable extra is optional; skip the suite without it


class _FakeLLM:
    async def complete(
        self, messages: list[dict[str, Any]], tools: Any = None, *, on_token: Any = None
    ) -> Any: ...

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type[Any]
    ) -> Any: ...


def test_configure_durable_sets_context() -> None:
    from argus.agent.budget import Budget
    from argus.agent.durable import _require_ctx, configure_durable, research_workflow
    from argus.tools.registry import ToolRegistry

    configure_durable(
        llm=_FakeLLM(),
        registry=ToolRegistry(),
        searcher_budget=Budget(max_turns=1, max_tokens=1, max_wallclock_s=1.0, max_cost_usd=0.1),
        ingested_sources=["a.md"],
        max_rounds=3,
        max_sub_questions=5,
    )
    context = _require_ctx()
    assert context.max_rounds == 3
    assert context.max_sub_questions == 5
    assert context.ingested_sources == ["a.md"]
    assert callable(research_workflow)  # the workflow is registered with DBOS


def test_require_ctx_raises_when_unconfigured() -> None:
    import argus.agent.durable as durable

    saved = durable._ctx
    durable._ctx = None
    try:
        with pytest.raises(RuntimeError):
            durable._require_ctx()
    finally:
        durable._ctx = saved
