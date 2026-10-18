FROM python:3.12-slim

# Set by the release pipeline; shown in /api/health, /api/config and the interface.
ARG BIZVIEW_VERSION=dev
# Repository address offered to every user (AGPL-3.0 §13); an installation may override it.
ARG BIZVIEW_SOURCE_URL=""
LABEL org.opencontainers.image.title="bizview-backend" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="${BIZVIEW_VERSION}" \
      org.opencontainers.image.source="${BIZVIEW_SOURCE_URL}"
ENV BIZVIEW_VERSION=${BIZVIEW_VERSION} SOURCE_URL=${BIZVIEW_SOURCE_URL}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

# Build context: repository root (the backend depends on the shared cli/ package).
WORKDIR /app/backend
COPY cli /app/cli
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --no-dev --no-install-project --frozen

COPY backend/ ./
RUN useradd --system --uid 10001 app && chmod +x entrypoint.sh \
    && mkdir -p /app/data/projects /app/data/workspace \
    && chown app:app /app/data/projects /app/data/workspace
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"
ENTRYPOINT ["./entrypoint.sh"]
