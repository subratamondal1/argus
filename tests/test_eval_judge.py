from __future__ import annotations

from typing import Any

from argus.eval.judge import Verdict, judge_answer, judge_messages


def test_judge_messages_include_all_three_parts() -> None:
    messages = judge_messages("the question", "the answer", "the context")
    user = messages[-1]["content"]
    assert "the question" in user
    assert "the answer" in user
    assert "the context" in user


async def test_judge_answer_returns_the_verdict() -> None:
    class FakeLLM:
        async def complete_structured(
            self, messages: list[dict[str, Any]], schema: type[Any]
        ) -> Any:
            assert schema is Verdict
            return Verdict(passed=True, reason="grounded in context")

    verdict = await judge_answer(FakeLLM(), question="q", answer="a", context="c")
    assert verdict.passed
    assert verdict.reason == "grounded in context"
