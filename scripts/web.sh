#!/usr/bin/env bash
# Run the Argus backend (FastAPI on :8000) and frontend (Next.js on :3000)
# together. Ctrl-C stops both. Postgres + SearXNG must already be up:
#   docker compose --profile data up -d
set -euo pipefail

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "argus: starting backend on http://localhost:8000 and frontend on http://localhost:3000"

uv run argus serve --reload &
( cd frontend && bun run dev ) &
wait
