"""Async load generator for the Argus HTTP API.

Fires a fixed number of requests at a target endpoint with bounded concurrency and
reports throughput + latency percentiles + error rate. Stdlib + httpx only, so it
runs without the app's dependencies on the load box.

    uv run python scripts/loadtest.py --path /api/health --concurrency 50 --requests 2000
    uv run python scripts/loadtest.py --path /api/ask --method POST \
        --body '{"question":"hi","deep":false}' --concurrency 8 --requests 40
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass

import httpx
import orjson


@dataclass(frozen=True)
class Sample:
    latency_ms: float
    status: int
    ok: bool


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered: list[float] = sorted(values)
    index: int = min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[index]


async def _one(client: httpx.AsyncClient, args: argparse.Namespace) -> Sample:
    started: float = time.perf_counter()
    try:
        response: httpx.Response = await client.request(
            args.method,
            args.path,
            content=args.body.encode() if args.body else None,
            headers={"content-type": "application/json"} if args.body else None,
        )
        elapsed_ms: float = (time.perf_counter() - started) * 1000.0
        return Sample(elapsed_ms, response.status_code, response.is_success)
    except Exception:
        return Sample((time.perf_counter() - started) * 1000.0, 0, ok=False)


async def _run(args: argparse.Namespace) -> int:
    semaphore = asyncio.Semaphore(args.concurrency)
    samples: list[Sample] = []

    async with httpx.AsyncClient(base_url=args.url, timeout=args.timeout) as client:

        async def worker() -> None:
            async with semaphore:
                samples.append(await _one(client, args))

        wall_started: float = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(args.requests)))
        wall_s: float = time.perf_counter() - wall_started

    latencies: list[float] = [sample.latency_ms for sample in samples]
    failures: int = sum(1 for sample in samples if not sample.ok)
    rps: float = len(samples) / wall_s if wall_s > 0 else 0.0
    report: list[str] = [
        f"target            {args.method} {args.url}{args.path}",
        f"requests          {len(samples)}  (concurrency {args.concurrency})",
        f"wall              {wall_s:.2f}s",
        f"throughput        {rps:.1f} req/s",
        f"errors            {failures}  ({100.0 * failures / max(1, len(samples)):.1f}%)",
        f"latency p50/p90   {_percentile(latencies, 50):.1f} / {_percentile(latencies, 90):.1f} ms",
        f"latency p95/p99   {_percentile(latencies, 95):.1f} / {_percentile(latencies, 99):.1f} ms",
        f"latency max       {max(latencies, default=0.0):.1f} ms",
    ]
    sys.stdout.write("\n".join(report) + "\n")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="loadtest", description="Load-test the Argus API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/api/health")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--body", default="", help="Request body (JSON) for POST.")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=30.0)
    arguments = parser.parse_args()
    if arguments.body:
        orjson.loads(arguments.body)  # fail fast on a malformed body
    return asyncio.run(_run(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
