FROM python:3.12-slim

# Set by the release pipeline; shown in /api/health, /api/config and the interface.
ARG BIZVIEW_VERSION=dev
# Commit the image is built from (deploy.sh passes it): /api/health reports it, so an installation
# can be asked which code it runs.
ARG BIZVIEW_COMMIT=
# Repository address offered to every user (AGPL-3.0 §13); an installation may override it.
ARG BIZVIEW_SOURCE_URL=""
LABEL org.opencontainers.image.title="bizview-backend" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="${BIZVIEW_VERSION}" \
      org.opencontainers.image.source="${BIZVIEW_SOURCE_URL}"
ENV BIZVIEW_VERSION=${BIZVIEW_VERSION} SOURCE_URL=${BIZVIEW_SOURCE_URL} \
    BIZVIEW_COMMIT=${BIZVIEW_COMMIT}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"
# uv gives up after 30 s per request; the multi-megabyte wheels (polars, lxml, pillow) do not fit in
# that on a slow link and the build fails with a network timeout rather than a dependency problem.
ENV UV_HTTP_TIMEOUT=600
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

# Build context: repository root (the backend depends on the shared cli/ package).
# `pack/` travels too: the cli's wheel force-includes it as `bizview_cli/starter_pack` (feature 057),
# and an editable install resolves it at `../pack/bizview-starter-pack` — the backend renders the
# starter pack at runtime, so a missing folder fails both the build and `/api/projects/starter`.
WORKDIR /app/backend
COPY cli /app/cli
COPY pack /app/pack
COPY backend/pyproject.toml backend/uv.lock ./
# The published image installs every source driver (feature 061); an image built without the
# extra lists that kind as unavailable with the reason instead of failing.
RUN uv sync --no-dev --no-install-project --frozen --extra sources

COPY backend/ ./
RUN useradd --system --uid 10001 app && chmod +x entrypoint.sh \
    && mkdir -p /app/data/projects /app/data/workspace /app/data/image-cache \
    && chown app:app /app/data/projects /app/data/workspace /app/data/image-cache
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"
ENTRYPOINT ["./entrypoint.sh"]
