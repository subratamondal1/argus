"""Concurrency benchmark for the hybrid RAG retrieval path (pgvector + RRF).

Seeds a synthetic corpus (embedded via the configured embedder, stored through the
real _store path — no LLM contextualization), then fires N concurrent retrieve()
calls and reports throughput + latency percentiles. Measures the retrieval tier in
isolation (DB + embed + RRF), the part of a deep-research run that isn't LLM-bound.

    uv run python scripts/bench_retrieval.py --seed 400 --concurrency 20 --requests 1000
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from argus.config import get_settings
from argus.db import close_pool, get_pool
from argus.logging import configure_logging
from argus.rag.embeddings import EmbedTask, embed_texts
from argus.rag.ingest import _store
from argus.rag.retriever import retrieve

_CORPUS: str = "bench"
_QUERIES: list[str] = [
    "kubernetes autoscaling",
    "hybrid retrieval reranking",
    "postgres vector index",
    "agent budget cost cap",
    "prompt injection defense",
]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered: list[float] = sorted(values)
    return ordered[min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1)))]


async def _seed(count: int) -> None:
    texts: list[str] = [
        f"Document {index}: notes on {_QUERIES[index % len(_QUERIES)]} and related infrastructure."
        for index in range(count)
    ]
    embeddings: list[list[float]] = await embed_texts(texts, task=EmbedTask.DOCUMENT)
    await _store(
        "bench://seed", _CORPUS, "v1", texts, embeddings, get_settings().embedding_model, "public"
    )


async def _purge() -> None:
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute("DELETE FROM chunks WHERE corpus = $1", _CORPUS)


async def _run(args: argparse.Namespace) -> int:
    await _purge()
    await _seed(args.seed)

    semaphore = asyncio.Semaphore(args.concurrency)
    latencies: list[float] = []
    failures: int = 0

    async def one(index: int) -> None:
        nonlocal failures
        async with semaphore:
            started: float = time.perf_counter()
            try:
                await retrieve(_QUERIES[index % len(_QUERIES)], corpus=_CORPUS)
                latencies.append((time.perf_counter() - started) * 1000.0)
            except Exception:
                failures += 1

    wall_started: float = time.perf_counter()
    await asyncio.gather(*(one(index) for index in range(args.requests)))
    wall_s: float = time.perf_counter() - wall_started
    await _purge()
    await close_pool()

    rps: float = len(latencies) / wall_s if wall_s > 0 else 0.0
    report: list[str] = [
        f"corpus            {args.seed} chunks  ({get_settings().embedding_model})",
        f"retrievals        {args.requests}  (concurrency {args.concurrency})",
        f"throughput        {rps:.1f} retrievals/s",
        f"errors            {failures}",
        f"latency p50/p90   {_percentile(latencies, 50):.1f} / {_percentile(latencies, 90):.1f} ms",
        f"latency p95/p99   {_percentile(latencies, 95):.1f} / {_percentile(latencies, 99):.1f} ms",
    ]
    sys.stdout.write("\n".join(report) + "\n")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="bench-retrieval", description="Benchmark RAG retrieval.")
    parser.add_argument("--seed", type=int, default=400, help="Synthetic chunks to seed.")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=1000)
    # Quiet the per-retrieval INFO logs so only the report prints (raise with
    # ARGUS_LOG_LEVEL=INFO to trace).
    settings = get_settings()
    configure_logging(level="WARNING", json=settings.log_json)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
