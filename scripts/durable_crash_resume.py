"""Crash-resume demo for Argus's DBOS durable execution (ARGUS_USE_DURABLE).

Proves the durability guarantee in Argus's exact setup: a workflow checkpoints each
step into the same Postgres Argus runs, and if the process dies mid-run, a fresh
process recovers it and resumes from the last completed step — without re-executing
the steps that already finished.

Run it (Postgres up; `uv sync --extra durable`):

    uv run python scripts/durable_crash_resume.py

It self-orchestrates: a child process starts a 2-step workflow and is hard-killed
after step one checkpoints; the parent then launches DBOS, which recovers the
pending workflow and runs only the remaining step. The same guarantee applies to the
real research workflow (argus.agent.durable) — it shares this DBOS instance and
checkpointing; a deterministic 2-step workflow is used here so the proof needs no LLM.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dbos import DBOS, DBOSConfig, SetWorkflowID

from argus.config import get_settings

_MARKER = Path("/tmp/argus_durable_demo.log")
_WFID = "argus-durable-demo"
_SCHEMA = "argus_dbos_demo"


def _record(line: str) -> None:
    with _MARKER.open("a") as handle:
        handle.write(line + "\n")


@DBOS.step()
def first_step() -> str:
    _record("first_step ran")
    return "first"


@DBOS.step()
def second_step() -> str:
    _record("second_step ran")
    return "second"


@DBOS.workflow()
def demo_workflow() -> str:
    one = first_step()
    if os.environ.get("ARGUS_DEMO_CRASH") == "1":
        _record("== hard crash here (after first_step checkpointed, before second_step) ==")
        os._exit(7)
    return f"{one}+{second_step()}"


def _launch() -> None:
    url = get_settings().database_url
    config: DBOSConfig = {
        "name": "argus-durable-demo",
        "database_url": url,
        "system_database_url": url,
        "dbos_system_schema": _SCHEMA,
        "log_level": "WARNING",
    }
    DBOS(config=config)
    DBOS.launch()


def _run_crashing_child() -> None:
    _launch()
    with SetWorkflowID(_WFID):
        demo_workflow()  # crashes inside before completing


def _recover_and_report() -> None:
    _launch()  # launch() recovers workflows a prior process left pending
    result = DBOS.retrieve_workflow(_WFID).get_result()
    DBOS.destroy()
    log = _MARKER.read_text().strip().splitlines()
    firsts = sum(1 for line in log if line == "first_step ran")
    print("\n--- crash-resume demo ---")
    print("\n".join(f"  {line}" for line in log))
    print(f"\nrecovered result : {result}  (expected 'first+second')")
    print(f"first_step runs  : {firsts}  (expected 1 — not re-executed on recovery)")
    ok = result == "first+second" and firsts == 1
    print("RESULT           :", "PASS — durable recovery works" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main() -> None:
    if os.environ.get("ARGUS_DEMO_CRASH") == "1":
        _run_crashing_child()
        return
    _MARKER.unlink(missing_ok=True)
    # Phase 1: a separate process starts the workflow and is killed mid-run.
    subprocess.run(
        [sys.executable, __file__], env={**os.environ, "ARGUS_DEMO_CRASH": "1"}, check=False
    )
    # Phase 2: this process recovers the pending workflow and finishes it.
    _recover_and_report()


if __name__ == "__main__":
    main()
