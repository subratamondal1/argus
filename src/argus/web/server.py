"""FastAPI HTTP API: streaming agent runs (SSE) + document ingest, for the web UI.

POST /api/ask streams the agent's progress events (plan, search, tool,
synthesize, answer) as Server-Sent Events, so the UI can render the multi-agent
flow live. The agent runs in a task that pushes events onto a queue; the SSE
generator drains the queue until a sentinel. The asyncpg pool is opened lazily on
first use and closed once on shutdown.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import orjson
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from argus.agent.events import AgentEvent
from argus.builders import build_loop, build_orchestrator
from argus.config import get_settings
from argus.db import close_pool
from argus.logging import configure_logging, get_logger
from argus.rag.ingest import ingest_source

log = get_logger(__name__)

_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    yield
    await close_pool()


app = FastAPI(title="Argus", version="0.0.1", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    deep: bool = False


class IngestRequest(BaseModel):
    source: str = Field(min_length=1)
    corpus: str = "default"


class IngestResponse(BaseModel):
    source_uri: str
    chunks_written: int


def _encode(event: AgentEvent) -> str:
    return orjson.dumps({"type": event.kind, **event.data}).decode()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": get_settings().model}


@app.post("/api/ask")
async def ask(request: AskRequest) -> EventSourceResponse:
    return EventSourceResponse(_ask_events(request))


async def _ask_events(request: AskRequest) -> AsyncIterator[dict[str, str]]:
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

    async def sink(event: AgentEvent) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            if request.deep:
                await build_orchestrator().run(request.question, on_event=sink)
            else:
                result = await build_loop().run(request.question, on_event=sink)
                await sink(AgentEvent("answer", {"text": result.answer}))
        except Exception as error:
            await sink(AgentEvent("error", {"message": f"{type(error).__name__}: {error}"}))
        finally:
            await queue.put(None)

    task: asyncio.Task[None] = asyncio.create_task(run())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {"data": _encode(event)}
        yield {"data": orjson.dumps({"type": "done"}).decode()}
    finally:
        task.cancel()


@app.post("/api/ingest")
async def ingest(request: IngestRequest) -> IngestResponse:
    result = await ingest_source(request.source, corpus=request.corpus)
    log.info("api_ingest", source=result.source_uri, chunks=result.chunks_written)
    return IngestResponse(source_uri=result.source_uri, chunks_written=result.chunks_written)
