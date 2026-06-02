"""System prompts and message builders for the agent and the orchestrator."""

from __future__ import annotations

from datetime import datetime


def research_system_prompt() -> str:
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


_PLANNER_SYSTEM: str = (
    "You are the planning step of a research system. Decompose the user's question into "
    "a small set of independent, specific sub-questions that, answered together, fully "
    "cover it. Prefer fewer, sharper sub-questions over many vague ones."
)

_SYNTHESIS_SYSTEM: str = (
    "You are the synthesis step of a research system. You are given the original question "
    "and findings from sub-researchers. Fuse them into one well-structured, cited answer. "
    "Use only the findings; do not invent facts. Prefer the most recent and most "
    "authoritative information, and cite the URLs the findings relied on."
)

_REFLECTION_SYSTEM: str = (
    "You are the reflection step of a research system. Given the question and a draft "
    "answer, decide whether the draft fully and correctly answers it. If anything is "
    "missing, stale, or unverified, list follow-up sub-questions that would close the gap. "
    "For 'latest' or 'most recent' questions be strict: mark complete only if the answer "
    "is verified against an authoritative, current source."
)


def planner_messages(question: str, max_sub_questions: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _PLANNER_SYSTEM},
        {
            "role": "user",
            "content": f"Question: {question}\nProduce at most {max_sub_questions} sub-questions.",
        },
    ]


def synthesis_messages(question: str, findings: list[tuple[str, str]]) -> list[dict[str, str]]:
    body: str = "\n\n".join(
        f"Sub-question: {sub_question}\nFinding: {answer}" for sub_question, answer in findings
    )
    return [
        {"role": "system", "content": _SYNTHESIS_SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nFindings:\n{body}"},
    ]


def reflection_messages(question: str, draft: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _REFLECTION_SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nDraft answer:\n{draft}"},
    ]
