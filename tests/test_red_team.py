from __future__ import annotations

from pathlib import Path

from argus.eval.red_team import RedTeamCase, load_red_team, run_red_team


async def test_run_red_team_flags_a_leaked_canary() -> None:
    cases = [
        RedTeamCase(name="resists", task="t", injection="i", canary="CANARY_X"),
        RedTeamCase(name="leaks", task="t", injection="i", canary="CANARY_Y"),
    ]

    async def fake(case: RedTeamCase) -> str:
        return (
            "I won't follow embedded instructions." if case.name == "resists" else "sure: CANARY_Y"
        )

    report = await run_red_team(cases, fake)

    assert report.n == 2
    assert report.resisted == 1
    assert not report.passed
    by_name = {result.name: result for result in report.results}
    assert by_name["resists"].resisted is True
    assert by_name["leaks"].resisted is False


async def test_run_red_team_passes_when_all_resist() -> None:
    cases = [RedTeamCase(name="a", task="t", injection="i", canary="ZZZ")]

    async def clean(case: RedTeamCase) -> str:
        return "Here is a faithful summary with no injected token."

    report = await run_red_team(cases, clean)
    assert report.passed
    assert report.resisted == 1


def test_red_team_dataset_loads() -> None:
    cases = load_red_team(Path("eval/red_team.jsonl"))
    assert len(cases) >= 4
    assert all(case.canary and case.task and case.injection for case in cases)
