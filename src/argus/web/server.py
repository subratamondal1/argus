"""FastAPI HTTP API: streaming agent runs (SSE) + document ingest, for the web UI.

POST /api/ask streams the agent's progress events (plan, search, tool,
synthesize, answer) as Server-Sent Events, so the UI can render the multi-agent
flow live. The agent runs in a task that pushes events onto a queue; the SSE
generator drains the queue until a sentinel. The asyncpg pool is opened lazily on
first use and closed once on shutdown.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import orjson
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from argus.agent.events import AgentEvent
from argus.agent.prompts import related_questions_messages
from argus.builders import build_adaptive
from argus.config import get_settings
from argus.db import close_pool
from argus.llm import LLMClient
from argus.logging import configure_logging, get_logger
from argus.rag.ingest import ingest_source

log = get_logger(__name__)


class _Related(BaseModel):
    questions: list[str]


async def _related_questions(question: str, answer: str) -> list[str]:
    if not answer.strip():
        return []
    settings = get_settings()
    llm = LLMClient(model=settings.model, timeout_s=settings.request_timeout_s)
    try:
        result = await llm.complete_structured(
            related_questions_messages(question, answer), _Related
        )
    except Exception as error:
        log.debug("related_failed", error=str(error))
        return []
    return [item for item in result.questions if item.strip()][:4]


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
            report = await build_adaptive().run(
                request.question, on_event=sink, force_research=request.deep
            )
            related = await _related_questions(request.question, report.answer)
            if related:
                await sink(AgentEvent("related", {"questions": related}))
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


def _persist_upload(name: str, data: bytes) -> str:
    directory: str = tempfile.mkdtemp(prefix="argus-upload-")
    path: str = os.path.join(directory, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


@app.post("/api/ingest/upload")
async def ingest_upload(file: Annotated[UploadFile, File()]) -> IngestResponse:
    name: str = Path(file.filename or "upload").name
    data: bytes = await file.read()
    path: str = await asyncio.to_thread(_persist_upload, name, data)
    result = await ingest_source(path, corpus="default")
    log.info("api_ingest_upload", file=name, chunks=result.chunks_written)
    return IngestResponse(source_uri=name, chunks_written=result.chunks_written)
