# AGENTS.md — Argus (canonical agent rules — read this FIRST)

> Single source of truth for AI coding agents (Codex, Cursor, Antigravity, Windsurf, Kimi, …) and humans. **EDIT THIS FILE.** Claude Code reads `CLAUDE.md`, a one-line `@AGENTS.md` shim that imports this verbatim — no duplication.

## What this is

**Argus** — a framework-free, multi-agent **deep-research engine**. A planner decomposes a question, fans out parallel research agents over the web and your ingested documents, and a synthesizer writes a **cited** answer. The agent runtime is hand-written (no agent framework); the generalized, productized form of that runtime is [bare-agent](https://github.com/subratamondal1/bare-agent).

## ⭐ THE INVARIANT (the reason this project exists)

```
Own the agent LOOP, not the framework.
- The tool-use loop is hand-written over LiteLLM. Nothing in a framework owns
  main(); the orchestrator is plain async Python you can read top to bottom.
- Every prompt + response is in plain sight (agent/prompts.py, the explicit
  messages list). No metaclass magic, no hidden DAG executor, no god-object.
- Extensibility = COMPOSITION. Seams are Python Protocols (CompletionClient,
  Approver, EventSink, TokenSink) — swap the LLM / approver / sink by passing a
  different object, never by configuring a closed framework.
- Multi-agent = a planner + N searchers + a synthesizer, each ONE agent loop.
  The fan-out is asyncio.gather (or arq workers); it is not a framework feature.
```

If a change hides control flow or traps state inside a framework abstraction, it is wrong — revert it.

## The pipeline (read in this order)

`agent/orchestrator.py` (plan → fan-out → synthesize) → `agent/loop.py` (the single hand-written tool-use loop, an `AsyncExitStack` + 3-axis budget + cycle-stop) → `agent/budget.py` (turns / tokens / wall-clock + hard cost cap) → `tools/registry.py` (self-registering, permission-gated dispatch) → `tools/{web_search,web_fetch,rag_search,execute_python}.py` → `agent/sources.py` (citation tracking) → `eval/` (the κ-calibrated LLM-judge gate that decides if an answer ships).

## Model: local-first, or bring your own frontier key (no lock-in)

Every LLM call goes through **LiteLLM**, so the model id picks the provider:
- **Local (default, $0, no key):** `ARGUS_MODEL=ollama_chat/qwen3` (or a larger local model). The eval suite even has a fully-local `qwen3.5:4b` column.
- **Frontier (your key):** `ARGUS_MODEL=anthropic/claude-sonnet-4-6` (or `openai/…`, `gemini/…`) + that provider's key in `.env`. Same loop, same tools.
- `ARGUS_FALLBACK_MODELS` (JSON list) is the retry ladder; `ARGUS_JUDGE_MODEL` MUST be a different model than the one under test (no grading your own homework).

## Stack (production-locked)

Python 3.12+ · `litellm` · Pydantic v2 · `pydantic-settings` (env prefix `ARGUS_`) · `structlog` · `orjson` · `httpx` + `trafilatura` (search/fetch) · **PostgreSQL + pgvector** via `asyncpg` (the RAG store) · `fastapi` + `uvicorn` + `sse-starlette` (the API + streaming) · **`arq` on Redis** (the searcher job queue, KEDA-autoscaled) · `argon2-cffi` + `pyjwt` (auth) · MCP server (`argus mcp`). Lazy extras: `parse` (docling), `rerank` (bge cross-encoder), `otel`. Tooling: `uv` · `ruff` · `ty` · `pytest` + `pytest-asyncio`.

## Forbidden abstractions (hard rules, every turn)

- **LLM frameworks**: NO LangChain, NO LangGraph, NO LlamaIndex, NO CrewAI, NO AutoGen. The hand-written loop IS the product.
- **Config**: NO `os.getenv()`. Only Pydantic Settings (`config.py`).
- **JSON**: NO stdlib `json`. Only `orjson`.
- **Logging**: NO `print()`. Only `structlog` (`get_logger`).
- **Type checking**: NO mypy, NO pyright. Only `ty`.
- **Tool args**: every tool takes exactly one Pydantic-model argument; its docstring is the LLM-facing description. A tool never crashes the loop — failures return `ToolResult(ok=False)`.

## Code style (architecture/03 standard — production, not teaching)

- The code reads like senior production code. **Full type annotations** on every variable, parameter, and return.
- **No narrative inline comments.** A terse module docstring states intent; the code explains itself. A `#` comment is justified only for a non-obvious *why* (a constraint, a footgun) — never to narrate *what* the next line does.
- Successful tool output is wrapped `<untrusted_tool_output>` for prompt-injection containment.
- This is a clean-room showcase: **zero proprietary/workplace code or data**. Everything here is original.

## Commands

```bash
make ci          # format-check → lint → typecheck → test  (run before every push)
make test        # pytest
make ask Q="…"   # one-shot research from the CLI
make research    # the full planner → fan-out → synthesizer pipeline
make serve       # the FastAPI app (web UI backend)
make web         # the frontend dev server (run make web-install once first)
make mcp         # expose the tool registry over MCP
make eval        # the κ-calibrated LLM-judge eval gate
make red-team    # adversarial eval pass
make up / down   # the Docker stack (Postgres + Redis + SearXNG + app)
```

After every change, run `make ci` locally before claiming done.

## Architecture notes (for changes that touch infra)

- **Search worker plane.** The API enqueues one arq job per sub-question; worker pods consume them and run one agent loop each. KEDA scales those workers **0→N→0** on a Redis-list backlog (`ARGUS_USE_QUEUE=true`). KEDA's `redis` scaler measures `LLEN`, but arq's queue is a Redis **sorted set** — so a side-marker **list** tracks the backlog; do not point KEDA at arq's own queue.
- **RAG store.** pgvector over `asyncpg`; the default `rag_search` path works without the heavy `rerank` extra.
- **Eval gate.** An answer ships only past the LLM-judge gate calibrated to human labels (Cohen's κ); the judge model is independent of the model under test.

## Commit discipline

- **Conventional commits**, recruiter-readable, atomic (one logical change per commit). Meaningful change → subject + body explaining WHAT / WHY / HOW; mechanical change → subject only.
- **No `Co-Authored-By` trailer.** This is a personal showcase repo.
- Never `git reset --hard` / `git checkout -- .` / `git push --force` without explicit approval.
- License: **MIT** (open showcase — maximize reads / stars / forks).
