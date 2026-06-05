"""LLM-as-judge: is an answer correct and grounded in the retrieved context?

The judge is only trustworthy once calibrated: cohen_kappa (metrics.py) against a
small human-labelled set must clear the gate's floor before its verdicts are
allowed to block a build.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class Verdict(BaseModel):
    passed: bool = Field(description="True if the answer is correct AND grounded in the context.")
    faithful: bool = Field(
        default=True,
        description="Grounded in the context with no hallucinated/unsupported claims (RAGAS faithfulness).",
    )
    relevant: bool = Field(
        default=True,
        description="Actually addresses the question, not evasive (RAGAS answer relevancy).",
    )
    reason: str = Field(description="One sentence justifying the verdict.")


class JudgeClient(Protocol):
    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: type[Any]
    ) -> Any: ...


_SYSTEM: str = (
    "You are a strict RAG evaluator. Given a question, a candidate answer, and the "
    "retrieved context the answer should rely on, return three judgments: "
    "faithful = the answer is fully grounded in the context with no unsupported or "
    "hallucinated claims; relevant = the answer actually addresses the question and is "
    "not evasive; passed = the answer is correct AND grounded. Mark passed=false if it "
    "is wrong, unsupported by the context, or evasive."
)


def judge_messages(question: str, answer: str, context: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Question:\n{question}\n\nAnswer:\n{answer}\n\nContext:\n{context}",
        },
    ]


async def judge_answer(llm: JudgeClient, *, question: str, answer: str, context: str) -> Verdict:
    return await llm.complete_structured(judge_messages(question, answer, context), Verdict)
