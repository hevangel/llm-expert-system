# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE=node:24.11.0-bookworm-slim@sha256:76d0ed0ed93bed4f4376211e9d8fddac4d8b3fbdb54cc45955696001a3c91152
ARG PYTHON_IMAGE=python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d

FROM ${NODE_IMAGE} AS web-builder
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts
COPY web/ ./
RUN npm run build

FROM ${PYTHON_IMAGE} AS python-builder
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /build
RUN python -m pip install --no-cache-dir uv==0.9.28
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable --extra engines --extra llm

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LLM_EXPERT_WORKSPACE=/data \
    LLM_EXPERT_API_HOST=0.0.0.0 \
    LLM_EXPERT_API_PORT=8000
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates swi-prolog-nox \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 expert \
    && useradd --uid 10001 --gid expert --create-home --shell /usr/sbin/nologin expert \
    && mkdir -p /app /data \
    && chown -R expert:expert /app /data
WORKDIR /app
COPY --from=python-builder --chown=expert:expert /app/.venv ./.venv
COPY --from=python-builder --chown=expert:expert /build/src ./src
COPY --from=web-builder --chown=expert:expert /build/web/dist ./web/dist
USER 10001:10001
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "llm_expert_system.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
