# --- Stage 1: build the React frontend -------------------------------------
FROM node:22-slim AS web

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Stage 2: Python runtime serving API + built frontend -------------------
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first so the layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY *.py ./
COPY --from=web /web/dist ./web/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8080 \
    LOGFIRE_IGNORE_NO_CONFIG=1

EXPOSE 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
