# Argus

**A framework-free, horizontally-autoscaled multi-agent deep-research engine. Own the loop, not the framework.**

You ask a hard question. A **planner** decomposes it into sub-questions; a fleet of
**lightweight searcher agents** — each a hand-written agent loop — scales up *from zero* as
Kubernetes pods, searches the live web in parallel, and a **synthesizer** fuses their findings
into a cited report. Every LLM call is traced, cost-attributed, and gated by an eval suite that
blocks bad merges in CI.

Argus is built to prove four things a single-agent app can't: **true horizontal scale** (KEDA
queue-depth autoscaling of lightweight agent pods), **multi-agent orchestration**, **sandboxed
code execution**, and a **full, forkable LLMOps + eval pipeline**.

> **Status: Phase 2b — contextual RAG.** The hand-written agent loop, permission-gated tool
> registry, and 3-axis budget now drive an in-process multi-agent orchestrator (plan → parallel
> searchers → synthesize → reflect/replan) and a local contextual-RAG pipeline: `argus ingest`
> builds a PostgreSQL + pgvector corpus, and a `rag_search` tool retrieves it alongside web
> search. Still single-process; the Kubernetes + KEDA autoscaling and the CI eval gate land in
> later phases (see the roadmap below). Built in the open, one atomic commit at a time.

## Why framework-free?

An agent is an LLM in a tool-use loop. Importing a graph framework (LangGraph, CrewAI, AutoGen)
hides exactly the substrate that's worth owning: the KV-cache breakpoints, the per-turn budget,
the retry/fallback ladder, the failure handling. Argus owns its ~loop end to end — and the
README's design notes say *why* at each fork (why framework-free here, why KEDA over CPU-HPA,
why these eval thresholds), because the judgment is the point, not the dependency count.

## The 8 framework-free primitives

The hire-bar for production agent engineering is being able to build these eight from scratch.
Argus implements each as a readable module; this table tracks where each one stands.

| # | Primitive | Where it lives | Status |
|---|---|---|---|
| 1 | Tool registry (self-registering, permission-gated, async dispatch) | [`tools/registry.py`](src/argus/tools/registry.py) | ✅ |
| 2 | Prompt assembly (typed segments, cache breakpoints) | `agent/prompt.py` | Phase 1 |
| 3 | Agent loop (3-axis budget + cost cap, `AsyncExitStack`) | [`agent/loop.py`](src/argus/agent/loop.py) · [`agent/budget.py`](src/argus/agent/budget.py) | ✅ |
| 4 | Retry / fallback ladder (5-step, over LiteLLM) | `llm.py` | Phase 1 |
| 5 | State + memory (L1 in-loop / L2 Redis / L3 durable) | `state/` | Phase 2 |
| 6 | HITL / permissions (deny / allow / ask, default-deny) | `tools/registry.py` (gate) | hook ✅, flow Phase 5 |
| 7 | Observability (structlog + OTel, cost per span) | [`logging.py`](src/argus/logging.py) | logging ✅, OTel Phase 1 |
| 8 | Eval gate (golden-set replay + κ-judge, CI-blocking) | `eval/` | Phase 3 |

## Quickstart (Phase 0)

```bash
# 1. Install (uv manages the Python 3.12 toolchain and the venv).
uv sync

# 2. Point LiteLLM at a provider.
cp .env.example .env && nano .env   # set ANTHROPIC_API_KEY (or another provider)

# 3. Start the local stack (self-hosted SearXNG, no API key).
#    Picks the first free port from 8080, writes it to .env, and is idempotent:
#    run it again and it just reports the live URL instead of starting a duplicate.
make up

# 4. Ask Argus a question.
uv run argus "What changed in the EU AI Act timeline in 2026?"   # or: make ask Q="..."

# Stack controls: `make status` (is it up, and where) · `make down` (stop it).
```

## Ingest your own documents (Phase 2b)

Argus can also answer from a local document corpus. Bring up PostgreSQL + pgvector
(the `data` compose profile, alongside SearXNG) and ingest files or URLs; embeddings
run locally on Ollama, so no document text leaves the machine.

```bash
# 1. Start Postgres + pgvector (also starts SearXNG).
docker compose --profile data up -d

# 2. Pull the local embedding model (one time).
ollama pull nomic-embed-text

# 3. Ingest a file or a URL into the corpus.
uv run argus ingest ./notes/architecture.md
uv run argus ingest https://example.com/post

# 4. Ask — the agent calls rag_search over your corpus and web_search for live facts.
uv run argus --deep "How does our architecture handle retries?"
```

Ingest is Anthropic-style **Contextual Retrieval**: each chunk is prefixed with
LLM-written context, embedded with `nomic-embed-text`, and indexed for both dense
(HNSW) and lexical (FTS) search. A query fuses the two with Reciprocal Rank Fusion,
with an optional `bge-reranker-v2-m3` cross-encoder stage
(`ARGUS_RERANK_ENABLED=true`, needs `uv sync --extra rerank`). PDF/DOCX/PPTX ingest
needs `uv sync --extra parse`. See [ADR 0001](docs/adr/0001-datastore-postgres-pgvector.md)
for why pgvector is the single store.

## Development

```bash
make format      # ruff format
make lint        # ruff check
make typecheck   # ty check
make test        # pytest (no network; the LLM and SearXNG are faked)
make ci          # format-check + lint + typecheck + test (what CI runs)
```

CI runs format-check, lint, type-check, and tests on every push and pull request.

## Build roadmap

Each phase is independently demo-able and committable — the repo is a credible artifact at every
phase boundary, not only at the end.

- **Phase 0 — Spine** ✅: hand-written loop + tool registry + budget + one search tool, green CI.
- **Phase 1 — Real agent loop** (in progress): web-fetch/extract ✅; still to come — the 5-step
  retry/fallback ladder, prompt assembly with cache breakpoints, Redis state, OpenTelemetry traces.
- **Phase 2 — Multi-agent** ✅ (in-process): planner / searcher / synthesizer with reflect/replan;
  next, distribute the searchers over an ARQ-on-Redis work queue.
- **Phase 2b — Contextual RAG** ✅: `argus ingest` builds a PostgreSQL + pgvector corpus with
  Anthropic-style contextual retrieval (nomic-embed + hybrid HNSW/FTS + RRF, optional bge
  cross-encoder rerank), exposed as a `rag_search` tool the agent uses alongside `web_search`.
  Embeddings + rerank run locally.
- **Phase 3 — Eval as a CI gate**: golden set + RAGAS retrieval metrics + κ-calibrated LLM-judge +
  a regression gate that blocks merges; self-hosted Langfuse + Phoenix. *The minimum hireable artifact.*
- **Phase 4 — Kubernetes + KEDA**: queue-depth scale-from-zero of lightweight searcher pods; the
  0→N→0 autoscale curve under a reproducible load test; chaos-kill proof of no dropped work.
- **Phase 5 — Durable execution + sandbox + MCP**: checkpoint/resume across pod eviction;
  sandboxed `execute_python` behind a human-in-the-loop gate; the registry exposed as an MCP server.
- **Phase 6 — Polish**: README top-fold demo, architecture docs, ADRs, and a documented
  failure-mode catalog.

## License

MIT — see [LICENSE](LICENSE). Fork it, run it, build on it.
