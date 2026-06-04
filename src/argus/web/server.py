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
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import orjson
import structlog
from fastapi import FastAPI, File, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sse_starlette.sse import EventSourceResponse

from argus.agent.events import AgentEvent
from argus.agent.prompts import related_questions_messages
from argus.auth import AuthError, AuthResult, decode_token, login, signup, tenant_from_authorization
from argus.builders import build_adaptive, build_llm
from argus.config import get_settings
from argus.conversations import (
    delete_conversation,
    get_conversation,
    list_conversations,
    upsert_conversation,
)
from argus.db import close_pool, get_pool
from argus.logging import configure_logging, get_logger
from argus.observability import setup_langfuse, setup_tracing
from argus.rag.ingest import IngestResult, ingest_source
from argus.web.errors import ApiError, install_error_handlers
from argus.web.middleware import RequestIdMiddleware
from argus.web.ratelimit import RateLimitMiddleware

log = get_logger(__name__)


class _Related(BaseModel):
    questions: list[str]


async def _related_questions(question: str, answer: str) -> list[str]:
    if not answer.strip():
        return []
    llm = build_llm(get_settings())
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
# Order matters (the last add is the OUTERMOST). Final stack, outer→inner:
# CORS → request-id → rate-limit → app — so a 429 still carries a request_id and
# CORS headers, and the limiter never runs before the id is bound.
app.add_middleware(RateLimitMiddleware, settings=get_settings())
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)
install_error_handlers(app)
setup_tracing(app, get_settings())
setup_langfuse(get_settings())


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    deep: bool = False
    ingested: list[str] = Field(
        default_factory=list,
        description="Sources the user added in this chat, so the agent can resolve 'it'/'this'.",
    )


class IngestRequest(BaseModel):
    source: str = Field(min_length=1)
    corpus: str = "default"


class IngestResponse(BaseModel):
    source_uri: str
    chunks_written: int


class AuthRequest(BaseModel):
    email: EmailStr
    # max_length caps the argon2 work a single request can trigger (DoS bound);
    # the 8-char signup minimum is enforced in argus.auth.signup.
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    id: str
    email: str
    tenant: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


def _auth_response(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        token=result.token,
        user=UserOut(id=result.user_id, email=result.email, tenant=result.tenant),
    )


class ConversationSummaryOut(BaseModel):
    id: str
    title: str
    updated_at: int  # epoch milliseconds, to match the UI's createdAt/Date.now()


class ConversationsOut(BaseModel):
    conversations: list[ConversationSummaryOut]


class ConversationOut(ConversationSummaryOut):
    # Turns are owned by the UI; the server persists and returns them verbatim.
    turns: list[dict[str, Any]]


class ConversationUpsert(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    turns: list[dict[str, Any]] = Field(default_factory=list)


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _resolve_tenant(authorization: str | None) -> str:
    # The verified JWT is the ONLY trusted tenant source. No Authorization header ->
    # the shared "public" corpus; a present-but-invalid token fails CLOSED (401)
    # rather than falling back to anything a client can set.
    if authorization is None:
        return "public"
    tenant: str | None = tenant_from_authorization(authorization)
    if tenant is None:
        raise ApiError(code="invalid_token", status=401, message="invalid or expired session")
    return tenant


def _require_tenant(authorization: str | None) -> str:
    # Server-side history belongs to an account: a real (non-"public") tenant.
    # Anonymous callers keep their history in the browser and are rejected here.
    tenant: str = _resolve_tenant(authorization)
    if tenant == "public":
        raise ApiError(code="unauthenticated", status=401, message="sign in to access history")
    return tenant


@app.post("/api/auth/signup")
async def auth_signup(request: AuthRequest) -> AuthResponse:
    try:
        result = await signup(request.email, request.password)
    except AuthError as error:
        raise ApiError(code="signup_failed", status=409, message=str(error)) from error
    return _auth_response(result)


@app.post("/api/auth/login")
async def auth_login(request: AuthRequest) -> AuthResponse:
    try:
        result = await login(request.email, request.password)
    except AuthError as error:
        raise ApiError(code="invalid_credentials", status=401, message=str(error)) from error
    return _auth_response(result)


@app.get("/api/auth/me")
async def auth_me(authorization: Annotated[str | None, Header()] = None) -> UserOut:
    claims: dict[str, object] | None = None
    if authorization and authorization.lower().startswith("bearer "):
        claims = decode_token(authorization.split(" ", 1)[1].strip())
    if claims is None:
        raise ApiError(code="unauthenticated", status=401, message="not signed in")
    sub, email, tenant = claims.get("sub"), claims.get("email"), claims.get("tenant")
    if not (isinstance(sub, str) and isinstance(email, str) and isinstance(tenant, str)):
        raise ApiError(code="unauthenticated", status=401, message="malformed session")
    return UserOut(id=sub, email=email, tenant=tenant)


@app.get("/api/conversations")
async def conversations_list(
    authorization: Annotated[str | None, Header()] = None,
) -> ConversationsOut:
    tenant: str = _require_tenant(authorization)
    summaries = await list_conversations(tenant)
    return ConversationsOut(
        conversations=[
            ConversationSummaryOut(
                id=item.id, title=item.title, updated_at=_epoch_ms(item.updated_at)
            )
            for item in summaries
        ]
    )


@app.get("/api/conversations/{conversation_id}")
async def conversations_get(
    conversation_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ConversationOut:
    tenant: str = _require_tenant(authorization)
    conversation = await get_conversation(tenant, conversation_id)
    if conversation is None:
        raise ApiError(code="not_found", status=404, message="no such conversation")
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        updated_at=_epoch_ms(conversation.updated_at),
        turns=conversation.turns,
    )


@app.put("/api/conversations/{conversation_id}")
async def conversations_put(
    conversation_id: str,
    request: ConversationUpsert,
    authorization: Annotated[str | None, Header()] = None,
) -> ConversationSummaryOut:
    tenant: str = _require_tenant(authorization)
    updated_at = await upsert_conversation(tenant, conversation_id, request.title, request.turns)
    if updated_at is None:
        raise ApiError(code="invalid_id", status=422, message="malformed conversation id")
    return ConversationSummaryOut(
        id=conversation_id, title=request.title, updated_at=_epoch_ms(updated_at)
    )


@app.delete("/api/conversations/{conversation_id}")
async def conversations_delete(
    conversation_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    tenant: str = _require_tenant(authorization)
    return {"ok": await delete_conversation(tenant, conversation_id)}


def _encode(event: AgentEvent) -> str:
    return orjson.dumps({"type": event.kind, **event.data}).decode()


@app.get("/api/health")
async def health() -> dict[str, str]:
    # Shallow liveness — stays up through a DB blip so a transient outage doesn't
    # get the pod killed. Readiness (below) is where the deep check lives.
    return {"status": "ok", "model": get_settings().model}


@app.get("/api/ready")
async def ready() -> dict[str, str]:
    # Deep readiness: the API can serve real traffic only once Postgres answers.
    try:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("SELECT 1")
    except Exception as error:
        log.warning("not_ready", error=str(error))
        raise ApiError(code="not_ready", status=503, message="database not reachable") from error
    return {"status": "ready"}


@app.post("/api/ask")
async def ask(
    request: AskRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> EventSourceResponse:
    return EventSourceResponse(_ask_events(request, _resolve_tenant(authorization)))


async def _ask_events(request: AskRequest, tenant: str) -> AsyncIterator[dict[str, str]]:
    # Bind a run id under the request id so the planner and every fanned-out
    # searcher coroutine (which inherit this context) thread back to one run.
    run_id: str = uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(run_id=run_id)
    log.info("ask", deep=request.deep, ingested=len(request.ingested))
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

    async def sink(event: AgentEvent) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            report = await build_adaptive(request.ingested, tenant=tenant).run(
                request.question, on_event=sink, force_research=request.deep
            )
            related = await _related_questions(request.question, report.answer)
            if related:
                await sink(AgentEvent("related", {"questions": related}))
        except Exception as error:
            log.warning("ask_failed", error=str(error))
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
        structlog.contextvars.unbind_contextvars("run_id")


@app.post("/api/ingest")
async def ingest(
    request: IngestRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> IngestResponse:
    result = await _ingest(
        request.source, corpus=request.corpus, tenant=_resolve_tenant(authorization)
    )
    return IngestResponse(source_uri=result.source_uri, chunks_written=result.chunks_written)


async def _ingest(source: str, *, corpus: str, tenant: str = "public") -> IngestResult:
    # Surface ingest/parse failures as a clean, coded 422 (which carries CORS
    # headers). The exact exception goes to the log, not the client, so internal
    # paths/details aren't leaked in the response.
    try:
        result = await ingest_source(source, corpus=corpus, tenant=tenant)
    except Exception as error:
        log.warning("api_ingest_failed", source=source, error=str(error))
        raise ApiError(
            code="unprocessable_source",
            status=422,
            message="Couldn't read that source — check the path/URL and that it has text.",
        ) from error
    log.info("api_ingest", source=result.source_uri, chunks=result.chunks_written)
    return result


def _persist_upload(name: str, data: bytes) -> str:
    directory: str = tempfile.mkdtemp(prefix="argus-upload-")
    path: str = os.path.join(directory, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


@app.post("/api/ingest/upload")
async def ingest_upload(
    file: Annotated[UploadFile, File()],
    authorization: Annotated[str | None, Header()] = None,
) -> IngestResponse:
    name: str = Path(file.filename or "upload").name
    data: bytes = await file.read()
    path: str = await asyncio.to_thread(_persist_upload, name, data)
    result = await _ingest(path, corpus="default", tenant=_resolve_tenant(authorization))
    log.info("api_ingest_upload", file=name, chunks=result.chunks_written)
    return IngestResponse(source_uri=name, chunks_written=result.chunks_written)
