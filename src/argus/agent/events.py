"""A lightweight event stream for surfacing agent progress to a UI.

The agent loop and orchestrator take an optional EventSink and call emit() at
milestones (turns, tool calls, planning, searching, synthesizing, the answer).
When the sink is None — the CLI path — emit() is a no-op, so the core behaves
exactly as before. The web layer passes a sink that pushes onto a queue and
relays each event over Server-Sent Events.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


EventSink = Callable[[AgentEvent], Awaitable[None]]


async def emit(sink: EventSink | None, kind: str, /, **data: Any) -> None:
    if sink is not None:
        await sink(AgentEvent(kind, data))
