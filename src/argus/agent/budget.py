"""Three-axis budget and hard cost cap for a single agent run."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class BudgetStop(StrEnum):
    TURNS = "max_turns"
    TOKENS = "max_tokens"
    WALLCLOCK = "max_wallclock_s"
    COST = "max_cost_usd"


@dataclass(frozen=True)
class Budget:
    max_turns: int
    max_tokens: int
    max_wallclock_s: float
    max_cost_usd: float


@dataclass
class BudgetState:
    budget: Budget
    turns: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    _start: float = field(default_factory=time.monotonic)

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._start

    def record_turn(self, *, tokens: int, cost_usd: float) -> None:
        self.turns += 1
        self.tokens += tokens
        self.cost_usd += cost_usd

    def exceeded(self) -> BudgetStop | None:
        if self.turns >= self.budget.max_turns:
            return BudgetStop.TURNS
        if self.tokens >= self.budget.max_tokens:
            return BudgetStop.TOKENS
        if self.elapsed_s >= self.budget.max_wallclock_s:
            return BudgetStop.WALLCLOCK
        if self.cost_usd >= self.budget.max_cost_usd:
            return BudgetStop.COST
        return None
