# Argus

[![CI](https://github.com/subratamondal1/argus/actions/workflows/ci.yml/badge.svg)](https://github.com/subratamondal1/argus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

A framework-free, multi-agent **deep-research engine**. A planner decomposes a
question into sub-questions; a fan-out of hand-written searcher agents researches
them in parallel over the live web and a local document corpus; a synthesizer fuses
the findings into a cited answer. Retrieval quality is enforced by an eval gate that
blocks regressions, the searcher fan-out autoscales from zero on Kubernetes, and a
research run can be made crash-resumable.

Built on Python 3.12, LiteLLM, PostgreSQL + pgvector, FastAPI, and Next.js — with no
agent framework (no LangChain/LangGraph): the agent loop, budget, and failure
handling are owned directly. **Local-first** — it runs at zero cost on Ollama;
OpenAI and Anthropic are optional drop-ins.

## Features

| Capability | Detail |
|---|---|
| **Framework-free agent loop** | Hand-written tool-use loop over LiteLLM with a 3-axis budget (turns / tokens / wall-clock) + hard cost cap, a retry/fallback ladder, and a self-registering, permission-gated tool registry. |
| **Multi-agent orchestration** | Planner → parallel searcher agents (isolated context each) → synthesizer → reflect/replan. |
| **Contextual RAG** | Anthropic-style contextual chunking; hybrid dense-HNSW + lexical-FTS retrieval fused with Reciprocal Rank Fusion; optional `bge-reranker-v2-m3` cross-encoder — all on a single pgvector store. |
| **Eval gate** | A curated, source-grounded benchmark with RAGAS-style metrics (context precision/recall, faithfulness, answer relevancy) + a Cohen's-κ-calibrated LLM judge; fails the build below committed thresholds. |
| **Horizontal scale** | Searcher fan-out on an ARQ-on-Redis queue; Kubernetes + KEDA scale searcher pods from zero on queue depth. |
| **Durable execution** | Opt-in DBOS workflows — a crashed research run resumes from its last checkpointed step (Postgres-backed). |
| **MCP server** | The tool registry exposed over the Model Context Protocol (`argus mcp`) for any MCP host. |
| **Multi-tenant + auth** | Email/password → argon2id + HS256 JWT in an httpOnly cookie with signed double-submit CSRF; per-tenant data isolation. |
| **Streaming UI** | FastAPI Server-Sent Events streaming live multi-agent progress to a Next.js 16 / React 19 client. |
| **Sandboxed code execution** | `execute_python` runs model-generated code in a subprocess sandbox (rlimits, timeout, no network) behind a permission gate. |

## Quickstart

```bash
# 1. Install (uv manages the Python 3.12 toolchain and the venv).
uv sync

# 2. Start the local backing stack (Postgres + pgvector, SearXNG).
make up

# 3. Run the LLM and embeddings locally on Ollama — zero cost, no API key.
ollama pull qwen2.5:3b && ollama pull nomic-embed-text

# 4. Ask.
uv run argus "What changed in the EU AI Act timeline in 2026?"   # or: make ask Q="..."
```

`cp .env.example .env` first if you want to override defaults. To use a hosted model,
set `OPENAI_API_KEY` and `ARGUS_MODEL=openai/...` in `.env` (see
[Configuration](#configuration)). Stack controls: `make status` / `make down`.

## How it works

```
question
   │  planner (LLM)
   ▼
sub-questions ──► searcher agent ─┐   each: own tool-use loop + budget,
              ──► searcher agent ─┤   rag_search over the corpus + web_search,
              ──► searcher agent ─┘   run in parallel (asyncio / ARQ+KEDA)
                       │ findings
                       ▼
                  synthesizer (LLM) ──► reflect/replan ──► cited answer
```

Every LLM call is structured-logged and cost-attributed; the agent loop stops on the
first of its turn/token/wall-clock/cost limits. The RAG path ingests documents with
LLM-written contextual prefixes, embeds them (locally on Ollama), and indexes for
both dense (HNSW) and lexical (full-text) search; a query fuses the two with
Reciprocal Rank Fusion. Design decisions are recorded as ADRs in [`docs/adr/`](docs/adr/)
(e.g. [why a single pgvector store](docs/adr/0001-datastore-postgres-pgvector.md)).

## Eval gate

Retrieval quality is a number, not a vibe. `argus eval` ingests a curated RAG/vector-search
corpus ([`eval/corpus/`](eval/corpus/)), runs a committed golden set
([`eval/golden.jsonl`](eval/golden.jsonl)) — 48 questions including negative/unanswerable
cases — through real retrieval and a judged agent answer, and exits non-zero when any
metric falls below [`eval/thresholds.json`](eval/thresholds.json).

```bash
make eval             # the gate (corpus-only; reports the metrics below)
make eval-calibrate   # prove the judge agrees with humans (Cohen's κ ≥ floor)
```

Latest run (`make eval`, 48-item benchmark, corpus-only):

| Metric (RAGAS vocabulary) | gpt-5.4-mini | qwen2.5:3b (local) | threshold |
|---|---|---|---|
| context_recall (hit@k) | 1.000 | 0.976 | ≥ 0.80 |
| context_precision | 0.662 | 0.624 | ≥ 0.20 |
| mrr | 0.948 | 0.952 | ≥ 0.60 |
| faithfulness | 0.976 | 1.000 | ≥ 0.70 |
| answer_relevancy | 1.000 | 0.690 | — |
| judge_pass_rate | 0.976 | 0.000 | ≥ 0.70 |
| keyword_pass_rate | 0.881 | 0.190 | ≥ 0.60 |
| abstention_rate (negatives declined) | 1.000 | 0.000 | ≥ 0.70 |
| **Gate** | **PASS** | FAIL | |

Metrics are implemented in-repo ([`eval/`](src/argus/eval/)), not via RAGAS, to stay
dependency-light and offline. Retrieval and generation signals are gated
independently, and negatives are scored by abstention (a faithful system must decline
what the corpus can't answer). The local 3B stack is a zero-cost dev loop; the
thresholds are tuned for a frontier model.

## Document ingestion (RAG)

```bash
ollama pull nomic-embed-text                       # one-time, local embeddings
uv run argus ingest ./notes/architecture.md        # a file
uv run argus ingest https://example.com/post       # or a URL
uv run argus --deep "How does our system handle retries?"
```

Embeddings and rerank run locally, so document text never leaves the machine.
PDF/DOCX/PPTX ingest needs `uv sync --extra parse`; the cross-encoder rerank stage
needs `uv sync --extra rerank` and `ARGUS_RERANK_ENABLED=true`.

## Web UI

```bash
make web-install   # first time only: install frontend deps (bun)
make web           # FastAPI on :8000 + Next.js on :3000 → http://localhost:3000
```

The UI streams the multi-agent flow live (plan → parallel search → tool calls →
synthesize → reflect) and renders a cited Markdown answer, with document upload and a
deep-research toggle. The backend is standalone — `make serve` runs the API alone, and
the CLI works without the UI.

## Configuration

Settings are read by [Pydantic Settings](src/argus/config.py) from the environment
(`ARGUS_` prefix) or `.env`. The defaults are fully local and free. Common overrides:

| Variable | Default | Purpose |
|---|---|---|
| `ARGUS_MODEL` | `ollama_chat/qwen2.5:3b` | Agent / contextualization / judge LLM (`openai/...` for hosted). |
| `ARGUS_EMBEDDING_MODEL` | `ollama/nomic-embed-text` | Embedding model (768-d; must match the column). |
| `ARGUS_USE_QUEUE` | `false` | Fan searchers onto the ARQ-on-Redis queue (KEDA-autoscalable). |
| `ARGUS_USE_DURABLE` | `false` | Run deep research as a crash-resumable DBOS workflow (`--extra durable`). |
| `ARGUS_RERANK_ENABLED` | `false` | Enable the cross-encoder rerank stage (`--extra rerank`). |

Optional extras: `parse` (document parsing), `rerank` (cross-encoder), `otel`
(OpenTelemetry), `durable` (DBOS), `mcp` (MCP server).

## Development

```bash
make ci          # format-check + lint (ruff) + typecheck (ty) + tests (pytest)
make test        # tests only — hermetic (LLM, DB, and search are faked/marker-gated)
make mcp         # run the tool registry as an MCP server over stdio   (or: argus mcp)
```

CI runs the hermetic suite plus a Postgres + Redis integration job and a kind + KEDA
autoscaling smoke on every push. Integration tests are behind a `pytest -m integration`
marker so the default suite needs no services.

## License

MIT — see [LICENSE](LICENSE).
