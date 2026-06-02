"""The Argus CLI entrypoint: argus "your research question" [--deep]."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from argus.builders import build_loop, build_orchestrator
from argus.config import get_settings
from argus.db import close_pool
from argus.eval.calibration import CalibrationResult
from argus.eval.harness import run_calibration, run_gate
from argus.eval.runner import EvalReport
from argus.logging import configure_logging, get_logger
from argus.rag.ingest import ingest_source


async def _run(question: str, *, deep: bool) -> int:
    log = get_logger(__name__)
    if deep:
        report = await build_orchestrator().run(question)
        sys.stdout.write(report.answer.rstrip() + "\n")
        log.info("done", mode="deep", rounds=report.rounds, findings=len(report.findings))
    else:
        result = await build_loop().run(question)
        sys.stdout.write(result.answer.rstrip() + "\n")
        log.info(
            "done",
            mode="single",
            stop_reason=result.stop_reason,
            turns=result.turns,
            tokens=result.tokens,
            cost_usd=result.cost_usd,
        )
    return 0


async def _run_ingest(source: str, *, corpus: str, corpus_version: str) -> int:
    log = get_logger(__name__)
    try:
        result = await ingest_source(source, corpus=corpus, corpus_version=corpus_version)
    finally:
        await close_pool()
    sys.stdout.write(f"ingested {result.chunks_written} chunks from {result.source_uri}\n")
    log.info("done", mode="ingest", source=result.source_uri, chunks=result.chunks_written)
    return 0


def _main_ask(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="argus", description="Ask Argus a research question.")
    parser.add_argument("question", help="The research question to answer.")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Use the multi-agent orchestrator (plan, search, synthesize, reflect).",
    )
    arguments = parser.parse_args(argv)
    return asyncio.run(_run(arguments.question, deep=arguments.deep))


def _main_ingest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="argus ingest", description="Ingest a document (path or URL) into the local corpus."
    )
    parser.add_argument("source", help="A file path or URL to ingest.")
    parser.add_argument("--corpus", default="default", help="Corpus name to ingest into.")
    parser.add_argument("--corpus-version", default="v1", help="Corpus version tag.")
    arguments = parser.parse_args(argv)
    return asyncio.run(
        _run_ingest(
            arguments.source, corpus=arguments.corpus, corpus_version=arguments.corpus_version
        )
    )


def _format_eval(report: EvalReport) -> str:
    status: str = "PASS" if report.passed else "FAIL"
    lines: list[str] = [
        f"eval {status}  (n={report.n})",
        f"  hit@k             {report.hit_at_k:.3f}",
        f"  precision@k       {report.precision_at_k:.3f}",
        f"  mrr               {report.mrr:.3f}",
        f"  judge_pass_rate   {report.judge_pass_rate:.3f}",
        f"  keyword_pass_rate {report.keyword_pass_rate:.3f}",
    ]
    lines.extend(f"  - {failure}" for failure in report.failures)
    return "\n".join(lines) + "\n"


def _format_calibration(result: CalibrationResult) -> str:
    status: str = "PASS" if result.passed else "FAIL"
    lines: list[str] = [
        f"judge calibration {status}  (n={result.n})",
        f"  cohen_kappa  {result.kappa:.3f}",
        f"  agreement    {result.agreement:.3f}",
    ]
    lines.extend(f"  - disagree: {item}" for item in result.disagreements)
    return "\n".join(lines) + "\n"


def _main_eval(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="argus eval", description="Run the golden-set eval gate against the live stack."
    )
    parser.add_argument("--golden", default="eval/golden.jsonl", help="Golden dataset (jsonl).")
    parser.add_argument("--thresholds", default="eval/thresholds.json", help="Gate thresholds.")
    parser.add_argument(
        "--report", default="eval/last_report.json", help="Where to write the report."
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Calibrate the judge against human labels (Cohen's kappa) instead of running the gate.",
    )
    parser.add_argument(
        "--calibration", default="eval/judge_calibration.jsonl", help="Human-labelled judge set."
    )
    arguments = parser.parse_args(argv)
    if arguments.calibrate:
        result = asyncio.run(
            run_calibration(Path(arguments.calibration), Path(arguments.thresholds))
        )
        sys.stdout.write(_format_calibration(result))
        return 0 if result.passed else 1
    report = asyncio.run(
        run_gate(Path(arguments.golden), Path(arguments.thresholds), Path(arguments.report))
    )
    sys.stdout.write(_format_eval(report))
    return 0 if report.passed else 1


def _main_serve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="argus serve", description="Serve the HTTP API (Server-Sent Events) for the web UI."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev).")
    arguments = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(
        "argus.web.server:app",
        host=arguments.host,
        port=arguments.port,
        reload=arguments.reload,
    )
    return 0


def _dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "ingest":
        return _main_ingest(argv[1:])
    if argv and argv[0] == "eval":
        return _main_eval(argv[1:])
    if argv and argv[0] == "serve":
        return _main_serve(argv[1:])
    return _main_ask(argv)


def main() -> None:
    load_dotenv()
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    try:
        code: int = _dispatch(sys.argv[1:])
    except RuntimeError as error:
        sys.stderr.write(f"error: {error}\n")
        raise SystemExit(1) from error
    raise SystemExit(code)


if __name__ == "__main__":
    main()
