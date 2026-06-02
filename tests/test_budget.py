from __future__ import annotations

import time

from argus.agent.budget import Budget, BudgetState, BudgetStop


def make_budget(**overrides: float) -> Budget:
    base: dict[str, float] = {
        "max_turns": 3,
        "max_tokens": 1000,
        "max_wallclock_s": 100.0,
        "max_cost_usd": 1.0,
    }
    base.update(overrides)
    return Budget(
        max_turns=int(base["max_turns"]),
        max_tokens=int(base["max_tokens"]),
        max_wallclock_s=base["max_wallclock_s"],
        max_cost_usd=base["max_cost_usd"],
    )


def test_fresh_state_is_within_budget() -> None:
    assert BudgetState(make_budget()).exceeded() is None


def test_turns_axis() -> None:
    state = BudgetState(make_budget(max_turns=2))
    state.record_turn(tokens=1, cost_usd=0.0)
    assert state.exceeded() is None
    state.record_turn(tokens=1, cost_usd=0.0)
    assert state.exceeded() is BudgetStop.TURNS


def test_tokens_axis() -> None:
    state = BudgetState(make_budget(max_tokens=100))
    state.record_turn(tokens=100, cost_usd=0.0)
    assert state.exceeded() is BudgetStop.TOKENS


def test_cost_axis() -> None:
    state = BudgetState(make_budget(max_cost_usd=0.5))
    state.record_turn(tokens=1, cost_usd=0.5)
    assert state.exceeded() is BudgetStop.COST


def test_wallclock_axis() -> None:
    state = BudgetState(make_budget(max_wallclock_s=0.001))
    time.sleep(0.002)
    assert state.exceeded() is BudgetStop.WALLCLOCK
