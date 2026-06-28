<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/eye_1f441-fe0f.png" width="110" alt="Argus" />
</p>

<h1 align="center">Argus</h1>

<p align="center">
  <strong>Own the agent loop, not the framework.</strong>
</p>

<p align="center">
  A framework-free, multi-agent deep-research engine — a planner fans out parallel<br/>
  agents over the web and your documents, and a synthesizer writes a cited answer.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/tests-150%20passing-brightgreen?style=flat" alt="Tests: 150 passing">
  <img src="https://img.shields.io/badge/local--first-Ollama-orange?style=flat" alt="Local-first">
</p>

<p align="center">
  <a href="#benchmark">Benchmark</a> •
  <a href="#evaluation-methodology">Eval methodology</a> •
  <a href="#features">Features</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#how-it-works">How it works</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#development">Development</a>
</p>

---

Argus answers a hard question the way a research team would: a **planner** breaks it into sub-questions, a fan-out of hand-written **searcher agents** researches them in parallel over the live web and a local document corpus, and a **synthesizer** writes a cited answer. Retrieval quality is enforced by an **eval gate** that blocks regressions, the searcher fan-out **autoscales from zero** on Kubernetes, and a run can be made **crash-resumable**.

Built on Python 3.12 · LiteLLM · PostgreSQL + pgvector · FastAPI · Next.js — with **no agent framework** (no LangChain/LangGraph): the loop, the budget, and the failure handling are owned directly. **Local-first** — it runs at zero cost on Ollama; OpenAI and Anthropic are optional drop-ins.

<p align="center">
  <img src="docs/assets/argus-demo.gif" width="100%" alt="Argus deep-research run: a planner decomposes the question into four sub-questions, four searcher agents run in parallel, and a synthesizer writes a cited answer — streamed live." />
</p>

<p align="center">
  <em>One <strong>Deep research</strong> run, end to end: the planner decomposes the question, four searcher agents fan out in parallel, and the synthesizer streams a cited answer — running locally on Ollama at zero cost.</em>
</p>

---

## Benchmark

> **Retrieval quality is a number, not a vibe.**

`argus eval` ingests a curated RAG corpus ([`eval/corpus/`](eval/corpus/)), runs a committed golden set ([`eval/golden.jsonl`](eval/golden.jsonl)) — **48 questions including negative/unanswerable cases** — through real retrieval and a judged agent answer, and exits non-zero when any metric falls below [`eval/thresholds.json`](eval/thresholds.json).

### Latest results (`make eval`, 48-item benchmark, corpus-only)

| Metric (RAGAS vocabulary) | gpt-5.4-mini | qwen3.5:4b (local, $0) | qwen2.5:3b (local, $0) | threshold |
|---|:---:|:---:|:---:|:---:|
| `context_recall` (hit@k) | **1.000** | 0.976 | 0.976 | ≥ 0.80 |
| `context_precision` | 0.662 | **0.676** | 0.624 | ≥ 0.20 |
| `mrr` | 0.948 | **0.952** | 0.952 | ≥ 0.60 |
| `faithfulness` | 0.976 | 0.976 | **1.000** | ≥ 0.70 |
| `answer_relevancy` | **1.000** | 0.976 | 0.690 | — |
| `judge_pass_rate` | **0.976** | 0.643 | 0.000 | ≥ 0.70 |
| `keyword_pass_rate` | **0.881** | 0.833 | 0.190 | ≥ 0.60 |
| `abstention_rate` (negatives declined) | **1.000** | 0.833 | 0.000 | ≥ 0.70 |
| **Gate** | ✅ **PASS** | ❌ FAIL (judge by 0.057) | ❌ FAIL | |

**Reading the table:**
- The hosted `gpt-5.4-mini` clears all 8 gates. The fully-local `qwen3.5:4b` ($0 stack) passes 7 of 8 — one notch of reasoning short on `judge_pass_rate`, with retrieval, faithfulness, and abstention all green.
- `qwen2.5:3b` collapses on negatives (`abstention_rate = 0.000`): it fabricates answers for every unanswerable question. This is where smaller models fail in production RAG.
- Retrieval and generation signals are gated **independently**, so a retrieval regression never hides behind a good answer.

```bash
make eval             # run the eval gate (reports the table above)
make eval-calibrate   # prove the judge agrees with humans (Cohen's κ ≥ floor)
```

---

## Evaluation methodology

### Why these metrics?

Argus implements the RAGAS vocabulary **in-repo** ([`eval/`](src/argus/eval/)) without the RAGAS library, to stay dependency-light and fully offline. Each metric targets a distinct failure mode in a RAG + agentic system:

| Metric | What failure it catches |
|---|---|
| `context_recall` | Retriever misses relevant chunks entirely |
| `context_precision` | Retriever floods context with noise, diluting signal |
| `mrr` | Relevant chunk exists but ranks low — hurts synthesis quality |
| `faithfulness` | Synthesizer hallucinates facts not grounded in retrieved context |
| `answer_relevancy` | Synthesizer answers a different question than was asked |
| `judge_pass_rate` | Holistic answer quality, as judged by a calibrated LLM judge |
| `keyword_pass_rate` | Answer covers the key factual entities from the golden reference |
| `abstention_rate` | System fabricates on unanswerable queries instead of declining |

### How the golden set was constructed

The 48-item golden set (`eval/golden.jsonl`) was built to stress every failure mode:

- **Positive cases** — questions with clear, corpus-grounded answers. Each has a reference answer and a set of required keywords.
- **Negative / unanswerable cases** — questions whose answers are not in the corpus. A faithful system must decline (output a refusal or "I don't know"). Any non-refusal on a negative case is scored as `abstention_rate = 0`, the harshest possible penalty.
- **Near-miss cases** — questions with partial corpus support, designed to expose `context_precision` failures where the retriever returns related but not sufficient chunks.

### How the LLM judge is calibrated

The judge is a prompted LLM that scores each (question, retrieved_context, answer) triple as pass/fail. Calibration works as follows:

1. A human-annotated sample of 20 triples is rated pass/fail by a human.
2. The judge is run on the same 20 triples.
3. **Cohen's κ** is computed between human and judge labels. κ ≥ 0.80 is required before the judge is trusted as a gate. If κ falls below the floor, the judge prompt is revised and recalibrated (`make eval-calibrate`).
4. The calibrated judge then scores the remaining benchmark items. This prevents the judge from becoming a rubber stamp — κ < 0.80 means the judge is not reliably capturing human quality signals.

### What the `qwen2.5:3b` failure reveals

The smallest local model scores `abstention_rate = 0.000` — it fabricates an answer for every unanswerable question in the benchmark. This is the canonical failure mode of RAG systems deployed without abstention testing: the model confidently answers questions the corpus cannot support. The benchmark's negative cases exist specifically to catch this before it reaches production.

Getting `qwen3.5:4b` through the gate required disabling Qwen3's default chain-of-thought (`reasoning_effort="disable"` → Ollama `think:false`), which reduced latency from ~84s to ~2s per call, while keeping thinking enabled for structured judge output — which Ollama drops when thinking is off. This asymmetry (thinking off for answers, on for judging) is documented in [`docs/adr/`](docs/adr/).

---

## Features

| Capability | Detail |
|---|---|
| **Framework-free agent loop** | Hand-written tool-use loop over LiteLLM with a 3-axis budget (turns / tokens / wall-clock) + hard cost cap, a retry/fallback ladder, and a self-registering, permission-gated tool registry. |
| **Multi-agent orchestration** | Planner → parallel searcher agents (isolated context each) → synthesizer → reflect/replan. |
| **Contextual RAG** | Anthropic-style contextual chunking; hybrid dense-HNSW + lexical-FTS retrieval fused with Reciprocal Rank Fusion; optional `bge-reranker-v2-m3` cross-encoder — all on a single pgvector store. |
| **Eval gate** | RAGAS-style metrics + Cohen's-κ-calibrated LLM judge; fails the build below committed thresholds. Full methodology above. |
| **Horizontal scale** | Searcher fan-out on an ARQ-on-Redis queue; Kubernetes + KEDA scale searcher pods from zero on queue depth. |
| **Durable execution** | Opt-in DBOS workflows — a crashed research run resumes from its last checkpointed step (Postgres-backed). |
| **MCP server** | The tool registry exposed over the Model Context Protocol (`argus mcp`) for any MCP host. |
| **Multi-tenant + auth** | Email/password → argon2id + HS256 JWT in an httpOnly cookie with signed double-submit CSRF; per-tenant data isolation. |
| **Streaming UI** | FastAPI Server-Sent Events streaming live multi-agent progress to a Next.js 16 / React 19 client. |
| **Sandboxed code execution** | `execute_python` runs model-generated code in a subprocess sandbox (rlimits, timeout, no network) behind a permission gate. |

---

## Quickstart

```bash
# 1. Install (uv manages the Python 3.12 toolchain and the venv).
uv sync

# 2. Start the local backing stack (Postgres + pgvector, SearXNG).
make up

# 3. Run the LLM and embeddings locally on Ollama — zero cost, no API key.
ollama pull qwen2.5:3b && ollama pull nomic-embed-text

# 4. Ask.
uv run argus "What changed in the EU AI Act timeline in 2026?"
```

`cp .env.example .env` first if you want to override defaults. To use a hosted model, set `OPENAI_API_KEY` and `ARGUS_MODEL=openai/...` in `.env`. Stack controls: `make status` / `make down`.

---

## How it works

```
question
   │  planner (LLM)
   ▼
sub-questions ──► searcher agent ─┐   each: own tool-use loop + budget,
              ──► searcher agent ─┤   rag_search over corpus + web_search,
              ──► searcher agent ─┘   run in parallel (asyncio / ARQ + KEDA)
                       │ findings
                       ▼
                  synthesizer (LLM) ──► reflect/replan ──► cited answer
```

Every LLM call is structured-logged and cost-attributed; the agent loop stops on the first of its turn/token/wall-clock/cost limits. The RAG path ingests documents with LLM-written contextual prefixes, embeds them locally on Ollama, and indexes for both dense (HNSW) and lexical (full-text) search; queries fuse the two with Reciprocal Rank Fusion.

Design decisions are recorded as ADRs in [`docs/adr/`](docs/adr/).

### Why no framework?

The loop is a **stateless reducer** over an explicit `messages: list[dict]`. That one decision pays three ways:

- **Testability** — feed a canned `messages` list (or a fake `CompletionClient`), assert. No live LLM needed for 150 tests.
- **Durability** — the list is serializable, so checkpoint it and resume after a crash (DBOS opt-in).
- **Debuggability** — every prompt is in plain sight. There is no metaclass, DAG executor, or hidden state to peel back when something fails.

---

## Document ingestion (RAG)

```bash
ollama pull nomic-embed-text                       # one-time, local embeddings
uv run argus ingest ./notes/architecture.md        # a file
uv run argus ingest https://example.com/post       # or a URL
uv run argus --deep "How does our system handle retries?"
```

Embeddings and rerank run locally — document text never leaves the machine. PDF/DOCX/PPTX ingest: `uv sync --extra parse`. Cross-encoder rerank: `uv sync --extra rerank` + `ARGUS_RERANK_ENABLED=true`.

---

## Web UI

```bash
make web-install   # first time only: install frontend deps (bun)
make web           # FastAPI on :8000 + Next.js on :3000 → http://localhost:3000
```

The UI streams the multi-agent flow live (plan → parallel search → tool calls → synthesize → reflect) and renders a cited Markdown answer, with document upload and a deep-research toggle. The backend is standalone — `make serve` runs the API alone, and the CLI works without the UI.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ARGUS_MODEL` | `ollama_chat/qwen2.5:3b` | Agent / contextualization / judge LLM (`openai/...` for hosted). |
| `ARGUS_EMBEDDING_MODEL` | `ollama/nomic-embed-text` | Embedding model (768-d; must match the column). |
| `ARGUS_USE_QUEUE` | `false` | Fan searchers onto the ARQ-on-Redis queue (KEDA-autoscalable). |
| `ARGUS_USE_DURABLE` | `false` | Run deep research as a crash-resumable DBOS workflow (`--extra durable`). |
| `ARGUS_RERANK_ENABLED` | `false` | Enable the cross-encoder rerank stage (`--extra rerank`). |

Optional extras: `parse` (document parsing), `rerank` (cross-encoder), `otel` (OpenTelemetry), `durable` (DBOS), `mcp` (MCP server).

---

## Development

```bash
make ci          # format-check + lint (ruff) + typecheck (ty) + tests (pytest)
make test        # tests only — hermetic (LLM, DB, and search are faked/marker-gated)
make eval        # run the eval gate
make eval-calibrate   # judge calibration (Cohen's κ)
make mcp         # run the tool registry as an MCP server over stdio
```

CI runs the hermetic suite plus a Postgres + Redis integration job and a kind + KEDA autoscaling smoke on every push. Integration tests are behind a `pytest -m integration` marker so the default suite needs no services.

---

## License

MIT — see [LICENSE](LICENSE).
