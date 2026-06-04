# syntax=docker/dockerfile:1.7
# Argus production image. Two stages: an Astral uv builder that resolves the
# locked dependency set into /app/.venv, and a slim python:3.12 runtime that
# carries only that prebuilt venv + the installed console script. The runtime
# never sees uv, build tools, or the source tree as editable code.

# ---------------------------------------------------------------------------
# Stage 1: builder — resolve deps from uv.lock and install the project.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.11.19-python3.12-trixie-slim AS builder

# Compile .pyc at build time (faster first request) and copy rather than
# hard-link out of the cache mount (cache and target live on different mounts).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Layer 1: dependencies only. Copying just the lockfile + manifest means this
# expensive layer is cached and reused on every build where deps are unchanged.
# --no-install-project keeps the project itself out of this layer; --no-dev
# drops the dev group (ruff/ty/pytest); --frozen fails if uv.lock is stale.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Layer 2: the project. Now the source is present, install argus itself
# (the console script `argus`) into the same venv. --no-editable bakes a real
# copy into site-packages so the runtime stage needs no /app/src on disk.
COPY src ./src
COPY README.md ./README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
# Stage 2: runtime — slim Python with only the prebuilt venv.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Non-root: create an unprivileged user that owns nothing it can mutate.
RUN groupadd --system --gid 1000 argus \
    && useradd --system --uid 1000 --gid argus --no-create-home --home-dir /app argus

WORKDIR /app

# The venv is relocatable because of --no-editable above: copy it wholesale and
# put its bin on PATH so `argus`, `uvicorn`, and python resolve from it.
COPY --from=builder --chown=argus:argus /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER argus

EXPOSE 8000

# Pure-Python probe so the slim runtime needs no curl/wget apt install. Hits the
# FastAPI GET /api/health route; a non-200 raises and the check reports failure.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

# Bind 0.0.0.0 so the port is reachable from outside the container.
CMD ["argus", "serve", "--host", "0.0.0.0", "--port", "8000"]
